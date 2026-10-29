# API

All endpoints are served by `dashboard/app.py`. The browser dashboard uses the
same API a script would; there is no separate internal interface.

Base URL: `http://127.0.0.1:8080` (override with `CONTENT_STUDIO_HOST` /
`CONTENT_STUDIO_PORT`).

## Conventions

- Requests and responses are JSON unless noted.
- Error responses use one shape: `{"error": "<message>"}`.
- Mutating requests must send `Content-Type: application/json` when they carry a
  body. Form-encoded bodies return `415`.
- Cross-origin `Origin` / non-same-site `Sec-Fetch-Site` values return `403`.
- When `CONTENT_STUDIO_TOKEN` is set, every request needs the token as
  `X-Content-Studio-Token: <token>`, the `cs_token` cookie, or `?token=<token>`.
  Missing/wrong tokens return `401 {"error": "unauthorized"}` for `/api/` paths.
- There is no API version prefix. Treat the action vocabulary and item schema as
  the contract; `docs/DATABASE.md` documents the stored shape.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Dashboard HTML. |
| `GET` | `/api/state` | Full pipeline state: all items and the activity log. |
| `GET` | `/api/item/<id>` | One item. |
| `POST` | `/api/idea` | Create an item from a topic. |
| `POST` | `/api/action/<id>` | Advance, regenerate, or publish an item. |
| `GET` | `/api/asset/<path>` | Serve a preview asset or text artifact. |
| `GET` | `/api/settings/providers` | List providers (masked keys) and the current mode. |
| `POST` | `/api/settings/providers` | Add a provider. |
| `PUT` | `/api/settings/providers/<provider_id>` | Update a provider. |
| `DELETE` | `/api/settings/providers/<provider_id>` | Delete a provider. |
| `POST` | `/api/settings/providers/<provider_id>/test` | Send one real completion to check the key. |

Pages (HTML): `/`, `/content-studio`, `/ideas`, `/content-pipeline`, `/assets`,
`/projects`, `/analytics`, and `/settings`. The six middle pages are
Coming-soon placeholders.

## Provider settings

### Shapes

Provider object (keys are masked; the raw key is never returned):

```json
{
  "id": "9f2c1b7a4d10",
  "name": "OpenRouter",
  "base_url": "https://openrouter.ai/api/v1",
  "model": "openrouter/free",
  "enabled": true,
  "is_default": true,
  "has_key": true,
  "api_key": "sk-or-...ab12",
  "api_key_last4": "ab12"
}
```

Mode object:

```json
{"mode": "live", "provider_id": "9f2c1b7a4d10", "provider": "OpenRouter", "model": "openrouter/free"}
{"mode": "mock", "reason": "No enabled provider with an API key is set as the default."}
```

### `GET /api/settings/providers`

`200 {"providers": [...], "mode": {...}}`. `500` when `providers.json` is
unreadable (`{"error": "..."}`); fix or remove the file.

### `POST /api/settings/providers`

Request:

```json
{"name": "OpenRouter",
 "base_url": "https://openrouter.ai/api/v1",
 "model": "openrouter/free",
 "api_key": "sk-or-v1-...",
 "enabled": true}
```

`201` with the provider object. The first provider automatically becomes the
default.

| Condition | Status | `error` |
|---|---|---|
| Missing `name`, `base_url`, `model`, or `api_key` | `400` | `<field> is required` |
| `base_url` not `https://`, or `http://` on a non-local host | `400` | `base_url must start with https:// (http:// is allowed only for localhost)` |
| Credentials, query, or fragment in `base_url` | `400` | validation message |
| Duplicate name (case-insensitive) | `400` | `a provider with that name already exists` |
| `CONTENT_STUDIO_SECRET_KEY` invalid | `400` | `... is not a valid Fernet key ...` |
| Body is not JSON (with a body) | `415` | `content-type must be application/json` |
| Cross-origin / non-same-site mutation | `403` | `... blocked` |

### `PUT /api/settings/providers/<provider_id>`

Accepts any subset of `name`, `base_url`, `model`, `api_key`, `enabled`, and
`is_default`. An **empty or omitted `api_key` keeps the stored ciphertext**; a
non-empty value re-encrypts and updates the mask. `{"is_default": true}`
promotes this provider and demotes the rest. `200` with the provider, `404` for
an unknown id, `400` for the validation failures above.

### `DELETE /api/settings/providers/<provider_id>`

`200 {"deleted": "<id>"}`. If the deleted provider was the default, the first
remaining enabled provider with a key is promoted (otherwise the first
remaining provider). `404` for an unknown id.

### `POST /api/settings/providers/<provider_id>/test`

Sends `Reply with the single word OK.` through the adapter (15s timeout, two
attempts).

```json
200 {"ok": true, "provider_id": "9f2c1b7a4d10", "message": "Provider responded successfully.", "reply": "OK"}
502 {"ok": false, "error": "Provider 'OpenRouter' rejected the API key (HTTP 401)."}
404 {"ok": false, "error": "provider not found"}
```

The error text is sanitized: it never contains the API key.

### Provider failures during generation

A failed default provider raises `LLMError`, which the app maps to:

```
502 {"error": "Provider 'Name' ..."}
```

The item is not advanced and is not silently re-generated in mock mode.

### `GET /api/state`

Returns the whole store. There is no pagination or filtering; the dataset is one
operator's pipeline.

```json
{
  "items": [
    {
      "id": 16,
      "topic": "Phase 3 check carousel",
      "stage": "done",
      "status": "published_local",
      "format": "CAROUSEL",
      "ideas": [],
      "copy": {"format": "CAROUSEL", "slides": [], "caption": "", "hashtags": ""},
      "design": {"provider": "local-pillow", "count": 3, "slides": []},
      "published": true,
      "created_at": "2026-10-29T10:00:00+00:00",
      "publish": {"mode": "mock", "target": "local", "message": "..."}
    }
  ],
  "activity": [
    {"time": "2026-10-29T10:04:00+00:00", "message": "Item 16 saved as local publish package (publisher: mock)"}
  ]
}
```

Items are newest-first. Activity is newest-first and capped at 100 entries.
The arrays are always present; a missing or corrupt state file yields
`{"items": [], "activity": []}`.

Status: `200`.

### `GET /api/item/<id>`

Returns one item object. Status: `200`, or `404 {"error": "not found"}`.

### `POST /api/idea`

Request:

```json
{"topic": "Kitchen storage habits"}
```

Creates an item at `stage=idea`, `status=pending_approval`, `published=false`,
with `ideas=[]`, `copy=null`, `design=null`, `format=null`, and a UTC
`created_at`. The id is `max(existing ids) + 1`. Also appends an activity entry.

Response: `200` with the new item.

| Condition | Status | `error` |
|---|---|---|
| Missing/blank `topic` | `400` | `topic required` |
| `topic` longer than 300 characters | `400` | `topic must be 300 characters or fewer` |
| Body is not JSON (with a body) | `415` | `content-type must be application/json` |
| Cross-origin request | `403` | `cross-origin request blocked` |
| Token configured but absent | `401` | `unauthorized` |

### `POST /api/action/<id>`

Request:

```json
{"action": "select_idea", "selected_idea": "5 Simple Vastu Changes You Can Make Today"}
```

Only `select_idea` needs an extra field. The action must be allowed at the
item's current stage (see the machine in `docs/ARCHITECTURE.md`).

| `action` | Allowed stage | Effect | Resulting stage |
|---|---|---|---|
| `approve_idea` | `idea`, `idea_review` | Atlas generates up to 7 ideas | `idea_review` |
| `select_idea` | `idea_review` | Vera writes canonical copy for the idea's format | `copy` |
| `approve_copy` | `copy` | Kite renders assets | `design` |
| `approve_design` | `design` | Marks ready for final approval | `publish` |
| `publish` | `publish` | Orin writes the local package | `done` |
| `reject` | `idea`, `idea_review`, `copy`, `design` | Regenerates the current stage's output | unchanged |

Response: `200` with the updated item, except for the errors below. A successful
action also appends one activity entry.

| Condition | Status | `error` |
|---|---|---|
| Unknown id | `404` | `not found` |
| Action not listed for the stage (including any action on `done`) | `400` | `action '<action>' is not allowed at stage '<stage>'` |
| Unknown action value | `400` | `action '<action>' is not allowed at stage '<stage>'` |
| `select_idea` without a title | `400` | `idea required` |
| Title not found in the item's ideas | `400` | `selected idea is not in this item's ideas` |
| Kite reported a render problem and produced no assets | `400` | `Kite could not render: <note>` |
| `reject` on `copy` with missing idea/format | `400` | `cannot regenerate copy: missing selected idea or format` |
| `reject` on `design` with no copy | `400` | `cannot regenerate design: no copy data` |
| `reject` on `publish`/`done` | `400` | `action 'reject' is not allowed at stage '<stage>'` |
| Publisher mode is not `mock` | `400` | `publisher '<mode>' is not available: real Meta Graph publishing is disabled ...` |

A failed action does not advance the item and, except for the publisher case,
does not write a state change. The publisher check happens before `save()` too.

`select_idea` matches the title exactly first, then case-insensitively exactly.
Substring matching is intentionally not supported (it could select the wrong
format when two ideas share a phrase).

### `GET /api/asset/<path>`

Serves previews and text artifacts. Allowed paths:

- `data/renders/...` under the configured data root (Kite output).
- `static/assets/...` (legacy assets).

A bare path is resolved under `static/assets/` for older callers.

| Condition | Status |
|---|---|
| Missing file | `404 {"error": "not found"}` |
| `..`, backslash, leading `/`, drive letter/colon, or empty path | `400 {"error": "invalid path"}` |
| Resolved path outside both allowlisted roots | `403 {"error": "path outside asset directories"}` |
| Valid file | `200` with the file bytes and a MIME type |

MIME types: `.png`, `.jpg`/`.jpeg`, `.gif`, `.webp`, `.svg`, `.txt`
(`text/plain; charset=utf-8`); anything else is `application/octet-stream`.

Some traversal payloads (for example `/api/asset/../state.json`) are normalized
by the HTTP layer before routing and therefore return `404` instead of reaching
the route's `400`. Both outcomes are safe; the route-level checks and the
resolved-path check are covered in `tests/test_security.py`.

## Status codes

| Code | Meaning in this API |
|---|---|
| `200` | Success. |
| `400` | Invalid input, illegal action for the stage, render failure, or refused publisher. |
| `401` | Token required or wrong. |
| `403` | Cross-origin/cross-site request, or asset outside the allowlist. |
| `404` | Unknown item, unknown asset, or normalized traversal path. |
| `415` | Mutating body was not JSON. |
| `500` | Unexpected agent/network failure (for example an imgbb upload error) or unreadable provider settings. |
| `502` | The configured model provider failed (auth, rate limit, timeout, 5xx). |

## Examples

PowerShell, local no-token mode:

```powershell
$item = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/api/idea `
  -ContentType application/json -Body '{"topic":"Kitchen storage habits"}'

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/action/$($item.id)" `
  -ContentType application/json -Body '{"action":"approve_idea"}'
```

With a token:

```powershell
$headers = @{ "X-Content-Studio-Token" = $env:CONTENT_STUDIO_TOKEN }
Invoke-RestMethod -Uri http://127.0.0.1:8080/api/state -Headers $headers
```

A full manual sequence is:

```
POST /api/idea                         -> stage=idea
POST /api/action/<id> approve_idea     -> stage=idea_review
POST /api/action/<id> select_idea      -> stage=copy
POST /api/action/<id> approve_copy     -> stage=design
POST /api/action/<id> approve_design   -> stage=publish
POST /api/action/<id> publish          -> stage=done
```

## Caching and polling

The API sends no cache headers of its own beyond the app-wide security headers.
The dashboard polls `/api/state` after every mutation. Clients should do the
same instead of assuming an action response is the only change.
