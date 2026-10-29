# Integrations

Content Studio has four external surfaces: model providers for text generation
(BYO key, configured in Settings), imgbb for optional image hosting, and
publishing. Publishing is deliberately local-only. Nothing else leaves the
machine.

| Integration | Required | Default state | Egress |
|---|---|---|---|
| Model provider (BYOK) | No | Mock mode until a default provider is saved | Only to the configured `base_url` |
| imgbb | No | Disabled when no key | Only with `IMGBB_API_KEY` |
| Instagram / Meta Graph | No | Disabled by design | None |

## Model providers (BYOK)

Text generation calls one OpenAI-compatible endpoint. The provider list lives in
`data/settings/providers.json` and is managed from `/settings`; it is not read
from `OPENROUTER_API_KEY` any more.

### Adapter contract

`core/providers.py::chat`:

```
POST {base_url}/chat/completions
Authorization: Bearer <decrypted provider key>
Content-Type: application/json

{"model": "<provider model>",
 "messages": [{"role": "user", "content": "<prompt>"}]}
```

- `base_url` must be `https://…` (plain `http://` is allowed only for
  `localhost` / `127.0.0.1` / `::1`) and must not contain credentials, a query,
  or a fragment.
- The response is read from `choices[0].message.content`.
- `429`, `500`, `502`, `503`, and `504` are retried with exponential backoff
  (three attempts by default, `Retry-After` honoured, capped at 5s). Timeouts,
  connection failures, `401`/`403`, `404`, and malformed responses raise a
  sanitized `ProviderError`.
- There is no streaming and no token-usage accounting.
- The general pipeline timeout is 120s; the Settings **Test** button uses a 15s
  timeout and two attempts.

### Verified provider endpoints (checked 2026-10-29)

| Preset | Base URL | Model | Auth | Status |
|---|---|---|---|---|
| OpenRouter | `https://openrouter.ai/api/v1` | `openrouter/free` | `Authorization: Bearer` | Verified against `openrouter.ai/docs/quickstart` and `openrouter.ai/docs/faq` (the FAQ documents the free-model router and its rate limits). |
| SenseNova | `https://token.sensenova.cn/v1` | `sensenova-6.7-flash-lite` | `Authorization: Bearer` | Verified against the official `OpenSenseNova/SenseNova6.7` `API.md`: OpenAI-compatible `/chat/completions`, key from the SenseNova console. The free token plan is advertised on the platform; it is not a contractual guarantee. |
| OmniRoute | deployment-specific | deployment-specific | `Authorization: Bearer` | OpenAI-compatible `POST /v1/chat/completions` is documented at `omniroute.online/api/`, but the host is self-hosted or supplied by Cheaper Inference. Shipped as a **custom** preset: enter your own URL and model ID. |
| Custom | any `https://…` | any | `Authorization: Bearer` | Works with any gateway that implements the same request/response shape. |

Only the first two are hardcoded presets. There is no implied free tier for a
custom provider.

### Storage and masking

- `data/settings/providers.json` holds `id`, `name`, `base_url`, `model`,
  `enabled`, `is_default`, the Fernet ciphertext in `api_key`, and
  `api_key_last4` for display.
- Keys are encrypted with `CONTENT_STUDIO_SECRET_KEY` (`cryptography`/Fernet).
  If the variable is missing when the first provider is saved, the app generates
  one and appends it to `.env` with a warning on stderr.
- The API and the UI only ever expose a mask: `sk-or-...ab12` for OpenRouter,
  `sk-...ab12` for SenseNova hosts, `...ab12` for anything else.
- A missing or invalid secret key on **decrypt** raises a clear error instead of
  silently minting a new key (which would make saved keys unreadable).

### Mode and failure behaviour

- The live path is used only when the **default** provider is `enabled` and has a
  stored key. Otherwise generation is deterministic mock output and no network
  call is made.
- If the default provider fails, `core/llm.py` raises `LLMError`; the API returns
  `502 {"error": "<sanitized message>"}` and the item is not advanced. There is
  **no** silent switch to mock or to another provider.
- Vera no longer swallows `LLMError` into `fallback_copy`; only parser/schema
  errors still fall back. That keeps a provider outage visible on the item.
- Retry from the UI after fixing the key/URL/model, or mark another provider as
  the default.

### Legacy variables

`OPENROUTER_API_KEY` / `OPENROUTER_MODEL` / `MOCK_MODE` still exist in
`config.py` so old `.env` files load without crashing, but `core/llm.py` ignores
them. Delete them to avoid confusing the running mode.

### Mock routing

When no default provider is configured, `generate(prompt)` matches the prompt
text, not a model:

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
| Generate ideas / copy with a default provider configured | That provider's `base_url` only. |
| Render with `IMGBB_API_KEY` set | imgbb, once per image. |
| Publish | None. Writes a local JSON file. |
| Load the dashboard or Settings | None beyond the app's own origin. |

The CSP restricts `connect-src` and `img-src` to the app origin (plus `data:`),
so the browser itself does not call the provider or imgbb; only the Python
process does.

## Secrets

- Provider keys live encrypted in `data/settings/providers.json`; the Fernet key
  is `CONTENT_STUDIO_SECRET_KEY` in `.env` or the environment.
- `IMGBB_API_KEY` and `CONTENT_STUDIO_TOKEN` still come from `.env` or the
  environment.
- `.env` is gitignored, and so is `data/settings/`. No secret is logged; startup
  prints mode, provider name, model, publisher, and debug state, never values.
- Never put a token in `docs/`, tests, or committed config.
- Rotate a provider key in Settings (leave the field blank to keep the current
  one). Rotating `CONTENT_STUDIO_SECRET_KEY` makes every stored key unreadable:
  re-enter each key after changing it.
