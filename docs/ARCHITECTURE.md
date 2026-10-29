# Architecture

Content Studio is a single-process Flask application that turns one topic into a
reviewed, locally published Instagram content package. Every transition is a
human approval gate, and every generated artifact is kept on disk.

The pipeline is:

```
Atlas (ideas) -> human review -> Vera (copy) -> human review
              -> Kite (design) -> human review -> Orin (publish)
```

Only the publisher is mocked. Rendering is real, and the LLM layer is live when
a default provider with an encrypted key is saved in Settings.

## Runtime topology

```
Browser (templates/index.html + static/style.css)
   |  fetch JSON / load images
   v
Flask app  (dashboard/app.py, binds 127.0.0.1:8080 by default)
   |-- core/state.py    JSON store, ids, activity, locking, atomic saves
   |-- core/models.py   canonical copy schemas
   |-- core/settings.py encrypted provider store, validation, default/mode
   |-- core/providers.py OpenAI-compatible adapter, retries, sanitized errors
   |-- core/llm.py      default provider call, or deterministic mock output
   |-- agents/atlas.py  topic -> idea list
   |-- agents/vera.py   idea + format -> canonical copy
   |-- agents/kite.py   copy -> PNG / text assets (Pillow)
   `-- agents/orin.py   approved item -> local publish package

data/                  JSON state, renders, published snapshots
```

There is no queue, database, worker, or cache. Every request does its work
inline and returns when the files are written. That is a deliberate fit for one
operator on one machine; the limits are listed in `docs/SECURITY.md` and the
residual risks in `docs/AUDIT_RESULT.md`.

## Module responsibilities

| Module | Responsibility |
|---|---|
| `run.py` | Entrypoint. Resolves host/port/debug from the environment, refuses a non-loopback bind without a token, starts Flask, prints the effective provider mode. |
| `config.py` | Loads `.env` without overriding real environment variables; exposes brand, token, publisher, imgbb key, and the legacy OpenRouter variables (no longer used for generation). |
| `core/state.py` | Data root resolution, `load()`/`save()`, max+1 ids, activity log, lock, atomic replace with Windows retries, corrupt-file fallback. |
| `core/models.py` | `SUPPORTED_FORMATS`, `normalize_copy()`, `fallback_copy()`. The single source of truth for copy field names. |
| `core/settings.py` | Provider CRUD in `data/settings/providers.json`, Fernet encrypt/decrypt, URL/field validation, mask, default provider, mode info, auto-generated `CONTENT_STUDIO_SECRET_KEY`. |
| `core/providers.py` | One OpenAI-compatible `POST {base_url}/chat/completions` adapter with Bearer auth, bounded retries, timeout, and sanitized `ProviderError` messages. |
| `core/llm.py` | `generate(prompt)`: the default provider in live mode, one deterministic mock router otherwise. Raises `LLMError` on provider failure. |
| `agents/atlas.py` | Builds the idea prompt, parses JSON or plain text, normalizes each idea, dedupes, keeps at most seven. |
| `agents/vera.py` | Builds a per-format prompt, parses section-based output, normalizes through `core.models`, falls back to valid copy on failure. |
| `agents/kite.py` | Validates copy, renders per-format assets into `data/renders/item_<id>/`, optionally uploads to imgbb, returns project-relative paths. |
| `agents/orin.py` | Mock publisher. Writes `data/published/item_<id>.json` and records mode/target; refuses non-mock modes. |
| `dashboard/app.py` | Routes, auth/CSRF guards, security headers, stage-action state machine, asset allowlist, provider settings endpoints, `LLMError` → 502. |
| `templates/index.html` | Dashboard markup and inline JavaScript: polling, approval queue, previews, event delegation. |
| `templates/_sidebar.html` | Shared sidebar partial. The server passes `active`; the matching link gets `class="active"` and `aria-current="page"`. |
| `templates/settings.html` | BYOK provider management: mode card, provider list with Test/Edit/Delete/Set default, add/edit form with presets. |
| `templates/coming_soon.html` | Shared placeholder layout for the six secondary sections. |
| `static/style.css` | Theme, layout, approval and preview styling. |

## Request lifecycle

1. `GET /` renders `templates/index.html`.
2. The page calls `GET /api/state` on load and after every action.
3. `POST /api/idea` validates `topic` (required, ≤ 300 characters) and calls
   `core.state.create_item()`. The new item starts at `stage=idea`.
4. `POST /api/action/<id>`:
   - `guard_request()` runs first: token auth when configured, then the
     same-origin JSON rule for mutating methods.
   - `action()` acquires `core.state.locked()`, so read-modify-write cycles are
     serialized.
   - `_handle_action()` loads state, finds the item, and rejects any action not
     listed for the current stage in `STAGE_ACTIONS`.
   - The relevant agent runs. Failures that the agent reports (rather than
     raises) are turned into `400` responses before anything is saved.
   - The item is mutated, activity is appended, and `save()` writes the whole
     state atomically.
5. `GET /api/asset/<path>` serves preview files from the two allowlisted roots.

## Provider settings lifecycle

`/settings` is a real page rendered with the current mode. The browser then
calls `GET /api/settings/providers` and re-renders the list after every change.

1. **Create:** `POST /api/settings/providers` validates name/URL/model/key,
   encrypts the key, and writes `data/settings/providers.json` atomically. The
   first provider becomes the default.
2. **Use:** `core/settings.default_provider()` returns the default only when it
   is enabled and has a stored key. `core/llm.generate()` then calls
   `core/providers.chat()`; otherwise it returns deterministic mock output.
3. **Test:** `POST /api/settings/providers/<id>/test` sends one short
   completion and returns `{ok: true, ...}` or a sanitized `502`.
4. **Update:** `PUT` accepts a subset; an empty `api_key` keeps the stored
   ciphertext.
5. **Delete:** the key and row are removed; if it was the default, the first
   remaining enabled provider with a key is promoted.

A provider failure raises `LLMError`, which the app maps to `502`; the item is
not advanced, and no other provider or mock output is used as a substitute.

## Stage and action machine

`STAGE_ACTIONS` in `dashboard/app.py` and the button builder in
`templates/index.html` share one vocabulary.

| Stage | Allowed actions | Result |
|---|---|---|
| `idea` | `approve_idea`, `reject` | `approve_idea` → `idea_review` with ideas. `reject` regenerates ideas and stays at `idea`. |
| `idea_review` | `select_idea`, `approve_idea`, `reject` | `select_idea` → `copy` (Vera runs). `approve_idea`/`reject` regenerate ideas, stay at `idea_review`. |
| `copy` | `approve_copy`, `reject` | `approve_copy` → `design` (Kite runs). `reject` regenerates copy, stays at `copy`. |
| `design` | `approve_design`, `reject` | `approve_design` → `publish`. `reject` re-renders, stays at `design`. |
| `publish` | `publish` | → `done`, `status=published_local`, Orin writes the package. |
| `done` | none | Terminal. |

Every item also carries `status`. The current code uses `pending_approval` while
work is waiting on a human and `published_local` at the end. The stylesheet and
some dashboard filters also understand a `rejected` value, but the server
currently has no rejected state: `reject` always regenerates and keeps the item
pending. This is intentional (reject means "try again"), not a missing endpoint.

## Data flow

```
topic
  |  create_item
  v
item{stage: idea}
  |  approve_idea -> atlas.run(topic)
  v
item.ideas[]  (title, problem, angle, format, format_reason)
  |  select_idea -> vera.run(title, format)
  v
item.format, item.copy  (canonical per-format dict)
  |  approve_copy -> kite.run(id, copy, format)
  v
item.design  ({provider, count, slides|frames|scenes|text_file, ...})
  |  approve_design
  v
item{stage: publish}
  |  publish -> orin(item)
  v
item{stage: done, publish:{mode, target}, published:true}
data/published/item_<id>.json
```

### Copy schemas

`core/models.py` defines exactly one shape per format. Both Vera (producer) and
Kite (consumer) call `normalize_copy()` on the boundary, so a renamed field
fails loudly instead of rendering a blank image. The fields are documented in
`docs/DATABASE.md`.

### Rendering

Kite renders locally with Pillow. No image leaves the machine unless
`IMGBB_API_KEY` is set.

| Format | Asset(s) | Canvas |
|---|---|---|
| `CAROUSEL` | `slide_1.png` … `slide_N.png` | 1080×1350 |
| `SINGLE_IMAGE` | `single_image.png` | 1080×1350 |
| `REEL` | `scene_N.png` + `scene_N.txt` | 1080×1920 |
| `INFOGRAPHIC` | `infographic.png` | 1080×1350 |
| `TEXT_POST` | `text_post.txt` | no image |
| `MEME` | `meme.png` | 1080×1350 |
| `STORY_POLL` | `frame_1.png` … `frame_N.png` | 1080×1920 |

All assets for an item live under `data/renders/item_<id>/`. `TEXT_POST` returns
`count=0` with a `text_file` and `text_preview`; the other formats return a
non-zero count.

## Path model

`core/state.py` resolves:

```
DATA = CONTENT_STUDIO_DATA_DIR, or <project>/data
```

`core/state.py`, `agents/kite.py`, `agents/orin.py`, and `/api/asset` all derive
their paths from that one value. Kite stores paths relative to `DATA.parent`,
which yields `data/renders/item_9/slide_1.png` in the default layout. The
dashboard converts that into `/api/asset/data/renders/...` and the route
resolves it under the configured render root, so moving the data directory does
not require rewriting state.

See D-012 and D-018 in `docs/DECISIONS.md`.

## Concurrency and crash safety

- One `threading.RLock` (`_SAVE_LOCK`) protects saves. `locked()` lets a route
  hold it across load → agent → mutate → save, so two approvals cannot
  interleave.
- `create_item()` takes the same lock around its own read-modify-write.
- `save()` writes to a temp file in the data directory, flushes, `fsync`s, then
  `os.replace`s the destination. On Windows a concurrent reader can hold the
  destination open, so the replace retries for up to 1 second before failing.
- `load()` treats a missing, empty, unreadable, or wrong-shaped `state.json` as
  an empty store. The app stays up, but the failure is silent; keep backups (see
  `docs/DATABASE.md`).

## Failure handling

| Failure | Behaviour |
|---|---|
| OpenRouter error in Vera | `vera.run()` catches it and returns `fallback_copy()` with `validation_error`; the pipeline continues with placeholder copy. |
| OpenRouter error in Atlas | Not caught. `approve_idea` returns a Flask `500`. |
| Unparseable Vera output | Normalized fallback copy; pipeline continues. |
| Invalid copy shape at Kite | Kite returns `{count: 0, note: ...}`; the API returns `400` and leaves the item at `copy`. |
| imgbb upload error | Not caught. The render request fails with a `500` after the local PNG is written. |
| Non-mock publisher | `PublishError` → `400`, item stays at `publish`, nothing is written. |
| Corrupt `state.json` | `load()` returns an empty store. |

## Security boundary

All routes pass through the same `before_request` guard. Localhost needs no
token; a non-loopback bind requires `CONTENT_STUDIO_TOKEN` before the server will
start. Mutations must be same-origin JSON, and assets are confined to two
directories. Details and limitations are in `docs/SECURITY.md`.

## Extension points

### Adding a format

1. Add the name to `SUPPORTED_FORMATS` in `core/models.py` and a normalization
   branch in `normalize_copy()` / `fallback_copy()`.
2. Add a Vera prompt section and a mock block in `core/llm.py` if mock coverage
   is required.
3. Add a Kite render branch and an output-folder test in
   `tests/test_renderer.py`.
4. Add the display label handling if the generic `replace('_', ' ')` is not
   enough, and extend the API format test.
5. Update `docs/DATABASE.md` and the canvas table above.

### Adding a publisher

`agents/orin.py` has one seam: `describe()` validates the configured mode and
`run()` writes the package. A real publisher needs a new mode in
`SUPPORTED_PUBLISHERS`, credential validation, a network client, and a distinct
terminal status. Until then, `published_local` is the only success status
(D-021).

### Adding a UI section

The sidebar links outside Dashboard are `nav-disabled` placeholders. Add a route
and remove the disabled attributes together; do not re-enable a link before its
view exists.
