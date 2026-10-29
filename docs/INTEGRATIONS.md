# Integrations

Content Studio has three external surfaces: OpenRouter for text generation,
imgbb for optional image hosting, and publishing. Publishing is deliberately
local-only. Nothing else leaves the machine.

| Integration | Required | Default state | Egress |
|---|---|---|---|
| OpenRouter | No | Mock mode when no key | Only with `OPENROUTER_API_KEY` |
| imgbb | No | Disabled when no key | Only with `IMGBB_API_KEY` |
| Instagram / Meta Graph | No | Disabled by design | None |

## OpenRouter

### Configuration

| Variable | Default | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | unset | Any non-empty value switches `MOCK_MODE` off. |
| `OPENROUTER_MODEL` | `openrouter/free` | Model slug sent with every request. |

`config.py` loads `.env` first, but real environment variables win. The key is
never hardcoded and `.env` is gitignored.

### Request

`core/llm.py::_real_generate`:

```
POST https://openrouter.ai/api/v1/chat/completions
Authorization: Bearer <OPENROUTER_API_KEY>
Content-Type: application/json

{"model": "<OPENROUTER_MODEL>",
 "messages": [{"role": "user", "content": "<prompt>"}]}
```

Timeout is 120 seconds. There is no streaming, retry, backoff, or token-usage
accounting. The response is read from `choices[0].message.content`.

Only free routing is used (`openrouter/free` by default). Do not point this at a
paid model without an explicit budget decision.

### Mode switch

`MOCK_MODE = not bool(OPENROUTER_API_KEY)`. There is no separate flag, so an
empty key is the supported way to guarantee no network call.

### Failure behaviour

| Caller | Behaviour on error |
|---|---|
| Vera | Catches the exception and returns `fallback_copy()` with `validation_error`; the item still reaches the copy stage with placeholder copy. |
| Atlas | Does not catch. `approve_idea` returns HTTP `500`; the item stays at its current stage. |

Retry an Atlas failure by clicking Generate Ideas again. Fixing the key or
network is the real remedy.

### Mock routing

When `MOCK_MODE` is true, `generate(prompt)` matches the prompt text, not a
model:

- Vera prompts contain `SELECTED FORMAT:` / `OUTPUT FORMAT - <FORMAT>`; the
  router reads the format name and returns that format's canned block from
  `_VERA_MOCK`.
- Atlas prompts are just the topic. A few topic keywords return a canned idea
  list; any other topic gets the generic fallback, which returns one idea per
  supported format. This is why every format is selectable in mock mode.

The mock output is deterministic on purpose: tests and the browser e2e depend on
it (D-009, D-011).

### Prompt/schema contract

Vera's prompt asks for sections such as `HEADLINE`, `CAPTION`, `HASHTAGS`, and
the parser maps them to the canonical dict in `core/models.py`. If you change a
field name, change the prompt, the parser, the mock block, and the model
together; `normalize_copy()` is the guard that turns drift into a visible
`ValueError`/fallback instead of a blank render.

## imgbb

### Configuration

| Variable | Default | Meaning |
|---|---|---|
| `IMGBB_API_KEY` | unset | Enables image uploads. |

### Request

Every successfully rendered image is passed to `_upload_imgbb()`:

```
POST https://api.imgbb.com/1/upload?key=<IMGBB_API_KEY>
Content-Type: multipart/form-data
body: image=<file>
```

Timeout is 120 seconds. The returned `data.url` is stored as the design entry's
`url`. With no key, `url` is `null` and no request is made.

### Implications

- Setting the key sends every generated image to a third party. Do not set it
  if the content is private.
- Upload errors are not caught. A rejected key or network failure turns the
  render action into a `500` after the local PNG has already been written.
  Remove the key to restore local-only operation.
- The app keeps the local file regardless of upload success; previews use
  `/api/asset`, not the imgbb URL.
- The URL is metadata for a future publisher; no current code consumes it.

## Publishing

### Current behaviour: mock only

`CONTENT_STUDIO_PUBLISHER` defaults to `mock`. `agents/orin.py` accepts exactly
that value:

```json
{"mode": "mock", "target": "local", "message": "Saved locally (mock publisher; no Instagram API call)."}
```

On publish it writes `data/published/item_<id>.json` — the full item including
the design paths and the publish metadata — and the API sets `stage=done`,
`status=published_local`, `published=true`.

Any other value (`instagram`, `meta`, `graph`, `live`, …) raises `PublishError`
before anything is saved. The API returns `400` with:

```
publisher '<mode>' is not available: real Meta Graph publishing is disabled
until the Instagram account and Meta app are confirmed. Use
CONTENT_STUDIO_PUBLISHER=mock (the default) to save a local package.
```

This is a safety property, not a temporary stub that silently degrades (D-021).

### Why real publishing is disabled

There is no confirmed Instagram professional account, no Meta app, no app
review, and no long-lived token. Building the client first would ship untested
network and credential code and would make the Publish button mean something
different without the operator noticing.

### What a real integration requires

If the account and app are confirmed, the change is deliberately larger than a
config flip:

1. **Account:** Instagram Business/Creator account linked to a Facebook Page.
2. **App:** Meta app with `instagram_content_publish` (and related) permissions,
   app review where required, and a long-lived access token.
3. **Assets:** the Graph API fetches media by public HTTPS URL. That means a
   publicly reachable host for renders (imgbb or another CDN), plus a decision
   about deleting them after publish.
4. **Flow:** create a media container (`POST /<ig-user-id>/media`), poll its
   status, then publish (`POST /<ig-user-id>/media_publish`). Carousels need one
   container per child plus a parent; Reels and Stories have different
   parameters.
5. **Safety:** token storage outside the repo, expiry/rotation, rate-limit and
   error handling, idempotency (do not double-post on retry), and an audit trail
   that distinguishes local from remote publishing.
6. **Contract change:** add the mode to `SUPPORTED_PUBLISHERS`, add a terminal
   status such as `published_remote`, and keep `mock` available for tests.

Until all of that is done and verified against a test account, the mock
publisher is the correct behaviour. Do not enable a partial integration by
editing the refusal away.

## Network and privacy summary

| Action | Network call |
|---|---|
| Create an idea, select an idea, render, preview | None. |
| Generate ideas / copy with a key set | OpenRouter. |
| Render with `IMGBB_API_KEY` set | imgbb, once per image. |
| Publish | None. Writes a local JSON file. |
| Load the dashboard | None beyond the app's own origin. |

The CSP restricts `connect-src` and `img-src` to the app origin (plus `data:`),
so the browser itself does not call OpenRouter or imgbb; only the Python process
does.

## Secrets

- `OPENROUTER_API_KEY`, `IMGBB_API_KEY`, `CONTENT_STUDIO_TOKEN` come from `.env`
  or the environment only.
- `.env` is gitignored. No secret is logged; startup prints mode, publisher, and
  debug state, not values.
- Never put a token in `docs/`, tests, or committed config.
- Rotate a key by changing `.env` and restarting the process; there is no hot
  reload.
