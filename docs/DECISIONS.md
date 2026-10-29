# Decisions

Phase-scoped decisions made without blocking on the user. Newest last.

## D-001 — Git root is the inner project folder

**Decision:** Initialise git in `D:\content_studio\content_studio`, not the outer
`D:\content_studio` container.

**Why:** All source, tests, docs, data and the existing `.gitignore` live in the
inner folder. Initialising at the outer folder would add a pointless nesting level
and make `docs/SETUP.md` paths ambiguous.

**Consequence:** The repository is named `content_studio` and its root contains
`run.py`, `agents/`, `core/`, `dashboard/`, `tests/` and `docs/`.

## D-002 — Reuse the existing Python 3.14.6 venv

**Decision:** Reuse `.venv` after verifying `pip install -r requirements.txt`
succeeds, instead of deleting and recreating it.

**Why:** The venv is already pinned to the interpreter that runs the app, and
recreating it would only discard a working environment. `.venv/` is gitignored, so
a fresh clone still follows the documented `py -m venv .venv` path.

## D-003 — Pin the installed versions and pytest 9.2.0

**Decision:** Pin `flask==3.1.3`, `requests==2.34.2`, `Pillow==12.3.0` and add
`pytest==9.2.0`.

**Evidence:** `pip list --format=freeze` in the baseline venv showed those exact
versions. PyPI reported pytest 9.2.0 as the latest release on 2026-10-27 with
`requires_python >=3.10` (verified at `https://pypi.org/pypi/pytest/json`).

**Consequence:** Baseline behaviour does not change; installs are reproducible.

## D-004 — Local git identity

**Decision:** Set repository-local `user.name = "Content Studio Dev"` and
`user.email = "dev@localhost"`.

**Why:** No global git identity was configured, and commits are required per phase.
These values are local to this repository only.

## D-005 — Back up `data/` before the first fix

**Decision:** Copy all of `data/` to `data/_backup_20261029_092442/` and verify the
`state.json` hash before making changes.

**Why:** The ground rules forbid deleting user data without a backup. The copy
contains 49 files and the state hash matches.

## D-006 — Keep `data/` untracked for now

**Decision:** Leave the existing `.gitignore` rule (`data/`) in place for Phase 0.

**Why:** Phase 3 narrows the ignore list to generated renders only. Committing live
state or publish packages now would mix user data with source history before the
storage layout is settled.

## D-007 — JSON storage stays until Phase 3

**Decision:** Defer the repository-interface and storage decision to Phase 3 as
instructed.

**Why:** Phase 1 fixes are UI-critical and must not be bundled with a storage
refactor.

## D-008 — One stage-aware action vocabulary

**Decision:** Use exactly six action names in both the browser and the server:
`approve_idea`, `select_idea`, `approve_copy`, `approve_design`, `publish`, and
`reject`. `dashboard/app.py` holds `STAGE_ACTIONS`; an action is accepted only at
the listed stages.

**Why:** The UI previously generated `approve_<stage>`, producing names such as
`approve_idea_review` that the server rejected with 400. A single explicit map
removes the mismatch and returns a descriptive error for stale or invalid
actions.

**Consequence:** `approve_idea` is also allowed at `idea_review` when an item
has no ideas, so a previously stuck item can be regenerated. `select_idea`
requires `selected_idea` and moves the item from `idea_review` to `copy`.

## D-009 — Mock Atlas has a generic fallback

**Decision:** If a topic matches none of the canned mock branches, Atlas returns
three generic ideas (CAROUSEL, SINGLE_IMAGE, TEXT_POST) derived from the topic
line.

**Why:** During acceptance, item 4 ("Easy morning routines for energy") matched
no mock branch and returned zero ideas, leaving the UI at "No ideas generated"
with no way forward. The fallback keeps any fresh topic usable in mock mode.

**Consequence:** Mock ideas are generic for unmatched topics. Real LLM mode is
unaffected.

## D-010 — One canonical copy schema per format

**Decision:** `core/models.py` owns the only copy shape for each of the seven
formats. Vera validates and normalizes its parser output through
`normalize_copy()` and returns `fallback_copy()` when parsing fails. Kite calls
`normalize_copy()` again at its boundary.

**Why:** Vera and Kite had drifted apart (`visual_direction` vs. other names,
REEL scenes as strings vs. dicts), which crashed the renderer and produced empty
previews. A shared schema makes field drift a test failure instead of a runtime
error.

**Consequence:** Adding or renaming a field requires changing `core/models.py`
first. Unknown fields are dropped at the boundary, so the LLM cannot smuggle
arbitrary keys into `state.json`.

## D-011 — Mock Vera routes on the format name, not keywords

**Decision:** `core/llm.py` reads the selected format from the exact
`OUTPUT FORMAT - <FORMAT>` line in Vera's prompt and returns the matching mock
block.

**Why:** Keyword matching on "caption" made every format return carousel copy,
so the browser flow could not exercise the other six renderers.

**Consequence:** The mock depends on that prompt line staying stable. A change to
`_build_format_prompt()` must keep the line or update the mock parser.

## D-012 — Render assets are project-relative and served through `/api/asset`

**Decision:** Kite stores paths such as `data/renders/item_9/slide_1.png`
(forward slashes, relative to the project root). `/api/asset` serves only
`data/renders/` and `static/assets/` and rejects absolute, drive-letter, or
`..` paths. The UI also rewrites legacy absolute Windows paths before requesting
them.

**Why:** Absolute Windows paths never resolved in the browser, so every preview
404'd, and a static-folder-only allowlist could not reach generated renders.

**Consequence:** Moving render output out of `data/renders/` requires updating
the allowlist. Old state entries with absolute paths keep working through the
UI rewrite.

## D-013 — `core/state.py` retries the atomic replace on Windows

**Decision:** Serialize `save()` with a process lock and retry `os.replace` up to
20 times (50 ms apart) when Windows reports `PermissionError`.

**Why:** `POST /api/idea` returned 500 with
`PermissionError: [WinError 5]` while another request was reading `state.json`.
Windows denies the replace while the destination has an open handle.

**Consequence:** Writes can take up to one extra second under contention but no
longer fail. Multi-process deployments still need a single writer; that belongs
to the storage phase.

## D-014 — Phase 3 covers data integrity, not a database migration

**Decision:** Keep `state.json` as the store for now and treat Phase 3 as data
integrity plus cleanup: serialized mutations, collision-free ids, validated
request bodies, and the leftover audit items. A repository interface or a real
database moves to a later phase, after the API surface is frozen.

**Why:** The pipeline is single-user and local. Concurrency and validation were
producing real 500s and wrong-format renders; a storage rewrite would add risk
without fixing a demonstrated failure.

**Consequence:** `core/state.py` stays the only module that reads or writes
`data/state.json`. Adding a database means reimplementing `load`, `save`,
`create_item`, `next_id`, and `locked`, plus the tests that patch those globals.

## D-015 — Ignore generated data, keep `data/` present

**Decision:** `.gitignore` ignores `data/state.json`, `data/.state-*.tmp`,
`data/renders/`, `data/published/`, `data/_backup_*/`, and `tests/artifacts/`
instead of the whole `data/` folder. `data/.gitkeep` is tracked.

**Why:** A blanket `data/` rule also hid the folder from a fresh clone, and live
pipeline state is operator data that should not enter source history.

**Consequence:** A fresh clone starts with an empty pipeline; `core/state.py`
recreates the folder on first run. Anyone who wants seed content must copy a
state file in explicitly.

## D-016 — Localhost by default, one shared token for anything else

**Decision:** Default bind is `127.0.0.1`, debug is off, and any non-loopback
bind requires `CONTENT_STUDIO_TOKEN`. Authentication is a single shared secret
presented as a header, a cookie, or a one-time `?token=` URL.

**Why:** The app runs an LLM pipeline that writes files and, in debug mode,
exposes an interactive console. A single-operator tool does not need accounts,
but it does need a hard stop before a network bind and a way to authorize remote
access.

**Consequence:** There is no user model and no per-item authorization. Rotating
the token and restarting revokes all clients. A multi-user deployment needs a
real auth layer and a WSGI server, both explicitly out of scope.

## D-017 — CSRF is blocked by requiring same-origin JSON

**Decision:** Mutating requests must send `application/json`, and `Origin` /
`Sec-Fetch-Site` must match the app when present. No CSRF token is issued.

**Why:** The frontend already sends JSON, so the rule costs nothing. A cross-site
HTML form cannot set that content type, and browsers mark cross-site `fetch`
calls with `Origin` and `Sec-Fetch-Site`, so both classic CSRF and scripted
cross-site posts are rejected at the guard.

**Consequence:** Any future form-based UI or non-browser client must send JSON and
an honest `Origin`. API tests that post form data will get `415` by design.

## D-018 — `CONTENT_STUDIO_DATA_DIR` is the one data-root override

**Decision:** `core/state.py` reads `CONTENT_STUDIO_DATA_DIR` (default
`<project>/data`). State, renders, publish snapshots, and the `/api/asset`
allowlist all derive from that resolved folder.

**Why:** Tests and the browser e2e need a real server without touching the
operator's pipeline. Threading a path argument through every agent would have
changed every call site; one environment variable keeps the production default
identical.

**Consequence:** The override must be set before Python imports `core.state`
(module-level constant). A process cannot switch data roots at runtime. Any new
module that writes data must import `DATA` from `core.state` instead of
recomputing `Path(__file__).parent.parent / "data"`.

## D-019 — e2e tests run a real server against a temporary data directory

**Decision:** The Playwright suite starts `run.py` as a subprocess on a free
port with `CONTENT_STUDIO_DATA_DIR=<tmp>`, then drives the UI with real clicks.
The default `pytest` run excludes e2e via `addopts = -m "not e2e"`; `pytest -m
e2e` runs only the browser suite.

**Why:** Mocking Flask or the network would not catch the class of bugs found in
Phases 1–5 (stale DOM listeners, hidden controls, asset 404s). Excluding e2e from
the default run keeps the fast suite usable while still making the browser flow a
first-class, repeatable check.

**Consequence:** `playwright install chromium` is a setup step (documented in
`docs/SETUP.md`). Artifacts land in the gitignored `tests/artifacts/`. CI must
install browser binaries or skip the marker.

## D-020 — REEL scene cards use the 1080×1920 canvas

**Decision:** Kite renders REEL scene cards at 1080×1920, matching
`STORY_POLL`, instead of the 1080×1350 feed canvas.

**Why:** Reels are vertical video. A 4:5 card cannot be used as a reel frame
without cropping, and Phase 2 had already flagged the mismatch as a renderer
fix.

**Consequence:** Previously published items keep their 1350-tall assets; only
new renders are vertical. Any downstream step that assumed 1080×1350 for REEL
must read the actual image size.

## D-021 — `mock` is the only publisher; everything else is refused

**Decision:** `CONTENT_STUDIO_PUBLISHER` defaults to `mock`, and
`agents/orin.py` supports only that value. It writes a local JSON package to
`<data>/published/` and records `{"mode": "mock", "target": "local"}` on the
item. Any other value makes the publish action return `400` and leaves the item
unpublished.

**Why:** There is no Meta Graph integration, no confirmed Instagram account, and
no app credentials. A quiet fallback would let the UI claim a publish that never
happened, and building the integration before the account is confirmed would
ship untestable network code and credential handling.

**Consequence:** Enabling real publishing is a deliberate code change: implement
the Graph client, add credential validation, extend `SUPPORTED_PUBLISHERS`, and
give the API a publish-status that distinguishes local from remote. Until then
`published_local` is the only terminal status.

## D-022 — Provider selection comes from `data/settings/providers.json`, not env

**Decision:** The live LLM path reads the default enabled provider from
`<data>/settings/providers.json`. `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, and
`MOCK_MODE` remain in `config.py` for backwards-compatible loading but are
ignored by generation.

**Why:** Two sources of truth would make the Settings page lie: a saved provider
could be silently overridden by a leftover env key, and removing a provider would
not necessarily leave live mode. One store keeps the UI, the startup banner, and
the actual request consistent.

**Consequence:** A user upgrading with an old `.env` stays in mock mode until
they add a provider in Settings. `docs/INTEGRATIONS.md` calls the legacy
variables out explicitly.

## D-023 — Every provider uses one OpenAI-compatible adapter

**Decision:** `core/providers.py` sends `POST {base_url}/chat/completions` with
`Authorization: Bearer <key>` for OpenRouter, SenseNova, OmniRoute, and custom
gateways. There is no per-provider SDK or request shape.

**Why:** All three verified providers document the OpenAI wire format. One
adapter means one retry policy, one error vocabulary, one sanitizer, and one set
of tests (D-024). An SDK would add dependencies and per-provider drift for no
capability the app uses.

**Consequence:** A provider that is not OpenAI-compatible cannot be added without
a new adapter branch. The four presets in the UI are conveniences that pre-fill
URL/model, not separate code paths.

## D-024 — Retry 429/5xx with bounded backoff; never retry auth errors

**Decision:** The adapter retries `429`, `500`, `502`, `503`, and `504` up to
three attempts with exponential backoff (`Retry-After` honoured, capped at 5
seconds). `401`, `403`, `404`, timeouts, and malformed responses fail immediately
with a sanitized `ProviderError`.

**Why:** Rate limits and transient 5xx are worth one more request. Retrying a bad
key or a bad URL only multiplies failures and delays the operator's feedback.
Timeouts are surfaced rather than retried because a second 120-second request is
worse than telling the operator.

**Consequence:** The Settings **Test** button uses two attempts and 15 seconds.
`tests/test_providers.py` drives a local HTTP server to prove retry counts,
`Retry-After` handling, and the timeout path.

## D-025 — Provider keys are Fernet-encrypted with an auto-generated secret

**Decision:** Keys are encrypted with `cryptography`'s Fernet using
`CONTENT_STUDIO_SECRET_KEY`. On the first save, if the variable is absent, the
app generates a key, appends it to `.env`, and sets it in the process
environment. Only `api_key_last4` is stored in plain text. A missing or invalid
key during decryption raises `SettingsError`; it never rotates silently.

**Why:** The requirement is that the raw key is never in JSON or the API.
Plaintext storage would leak the key with any backup or support bundle. Silent
rotation would turn "key missing" into "all saved providers are broken" with no
explanation.

**Consequence:** `.env` becomes a required local file once a provider exists, and
`data/settings/` is gitignored. Losing `CONTENT_STUDIO_SECRET_KEY` means
re-entering every provider key. `tests/test_settings.py` asserts the round-trip,
the absence of the raw key, and the no-rotation failure.

## D-026 — Provider mask derives the prefix from the host

**Decision:** The UI shows `sk-or-...<last4>` for `openrouter.ai`,
`sk-...<last4>` for `*.sensenova.cn`, and `...<last4>` for any other host. Only
the last four characters are stored.

**Why:** The requirement asks for a hint shaped like `sk-or-...ab12`. Storing a
provider-specific prefix would add another plaintext fragment; deriving it from
the base URL keeps the file minimal and still produces the expected string.

**Consequence:** Changing a provider's base URL changes the displayed prefix. The
mask is a display hint, not a validator; the only proof of a working key is the
**Test** button.

## D-027 — OmniRoute is a custom preset; SenseNova is a fixed preset

**Decision:** OpenRouter and SenseNova ship with verified base URLs and model
IDs. OmniRoute ships as a preset that leaves the URL and model blank with a note,
because its endpoint is self-hosted or supplied by Cheaper Inference.

**Why:** Hardcoding a deployment-specific host would send keys to the wrong
place. The verification pass on 2026-10-29 found OmniRoute documents the
OpenAI-compatible `/v1/chat/completions` shape but no single public base URL, so
the safe choice is to make the operator fill it in.

**Consequence:** Selecting OmniRoute does not change the request shape; it only
shows the guidance note. `docs/INTEGRATIONS.md` records which endpoints are
verified and which are not.

## D-028 — A provider failure is a 502, never a silent mock fallback

**Decision:** `core/llm.py` raises `LLMError` when the default provider fails.
`dashboard/app.py` maps it to `502 {"error": "<sanitized message>"}`. Vera
re-raises `LLMError` instead of substituting `fallback_copy`. With no provider
configured, generation stays in deterministic mock mode.

**Why:** A silent switch hides an outage and produces content the operator
believes was model-written. The requirement is explicit: a default-provider
failure must show a clear item error and must not switch providers.

**Consequence:** Parser/schema problems still fall back to `fallback_copy()`
(unchanged), but transport/auth/rate-limit failures reach the UI. The item is not
advanced and can be retried after fixing Settings.
