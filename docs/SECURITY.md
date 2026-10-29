# Security

Content Studio is a local, single-operator tool. The security model is built
around that assumption: it is safe by default on `127.0.0.1`, and exposing it
elsewhere is an explicit, token-protected decision.

## Supported deployment

| Setting | Default | Meaning |
|---|---|---|
| `CONTENT_STUDIO_HOST` | `127.0.0.1` | Bind address. |
| `CONTENT_STUDIO_PORT` | `8080` | Bind port. |
| `CONTENT_STUDIO_DEBUG` | unset (off) | Enables the Werkzeug reloader **and** the interactive debugger. |
| `CONTENT_STUDIO_TOKEN` | unset | Shared secret required when binding a non-loopback address. |

`run.py` refuses to start when `CONTENT_STUDIO_HOST` is not `127.0.0.1`, `::1`,
or `localhost` and `CONTENT_STUDIO_TOKEN` is empty:

```
Refusing to bind 0.0.0.0: set CONTENT_STUDIO_TOKEN before exposing Content
Studio beyond localhost.
```

Debug mode is off by default. The Werkzeug debugger allows arbitrary code
execution from the browser, so `CONTENT_STUDIO_DEBUG=1` is only for local
development and must never be combined with a non-loopback bind.

## Controls implemented

### 1. Shared-token authentication (non-localhost)

When `CONTENT_STUDIO_TOKEN` is set, every request must present the token as:

- `X-Content-Studio-Token: <token>` (API clients), or
- the `cs_token` cookie (browser), or
- `GET /?token=<token>` once, which sets the cookie and redirects to `/`.

The cookie is `HttpOnly`, `SameSite=Strict`, and `Secure` when the request is
HTTPS. Comparison uses `hmac.compare_digest`. API requests without a valid token
return `401 {"error": "unauthorized"}`; page requests return `401` with a short
instruction.

Trade-off: a token in the query string can appear in server logs or browser
history. Prefer opening the token URL once on a trusted machine and then using
the cookie.

### 2. CSRF protection

State-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`) must:

- send `Content-Type: application/json` when they carry a body, and
- have an `Origin` header that matches the request host, when present, and
- have a `Sec-Fetch-Site` header in `same-origin`, `same-site`, or `none`, when
  present.

A cross-site HTML form cannot set `application/json`, and browsers attach
`Origin`/`Sec-Fetch-Site` to cross-site `fetch` calls, so both classic form CSRF
and scripted cross-site posts are rejected (`415` and `403` respectively).
Requests without a body skip the content-type rule so route-level validation
still returns its own error.

### 3. Path-traversal protection on `/api/asset`

Generated previews are served from two allowlisted roots only:

```
data/renders/
static/assets/
```

The route rejects any filename containing `..`, a backslash, a drive letter
(`:`), or a leading `/`. It resolves the real path and re-checks that it stays
inside an allowlisted root before reading the file. Bare paths are interpreted
relative to `static/assets/` for legacy callers.

Covered by `tests/test_security.py`:

- `/api/asset/../state.json` → rejected
- `/api/asset/data/renders/../../state.json` → rejected
- `/api/asset/static/assets/../../secret.txt` → rejected
- `/api/asset/C:/Windows/win.ini` → rejected
- `/api/asset/%2e%2e/state.json` and `/api/asset/..%2Fstate.json` → rejected
- `/api/asset/state.json` → not served

### 4. Input validation

- `POST /api/idea`: JSON body required, `topic` required, 300-character cap.
- `POST /api/action/<id>`: JSON body, action must be allowed at the item's
  current stage (`STAGE_ACTIONS`), `selected_idea` must match an idea title
  exactly (case-insensitive exact match as a fallback), and the selected format
  is validated against `SUPPORTED_FORMATS`.
- Kite render failures return `400` instead of storing an empty design.
- `POST/PUT /api/settings/providers`: `name`, `base_url`, `model`, and (on
  create) `api_key` are required; `base_url` must be `https://` except on
  localhost, with no credentials/query/fragment; names must be unique
  (case-insensitive); keys are capped at 4096 characters; unknown fields are
  ignored.

### 5. Response headers

Every response carries:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Content-Security-Policy: default-src 'self'; img-src 'self' data:;
  style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline';
  connect-src 'self'; frame-ancestors 'none'; base-uri 'none'
```

`'unsafe-inline'` is required because the dashboard ships one inline `<script>`
block and inline `style` attributes. Everything else is restricted to the app's
own origin, so remote scripts, remote styles, and remote `fetch` targets are
blocked.

### 6. Secrets

- Model-provider keys are entered in Settings and encrypted at rest with Fernet
  under `data/settings/providers.json`. The encryption key is
  `CONTENT_STUDIO_SECRET_KEY`.
- If the key is missing when the first provider is saved, `core/settings.py`
  generates one and appends `CONTENT_STUDIO_SECRET_KEY=<key>` to `.env`, then
  sets it in the process environment. Startup prints a warning, never the key.
- If the key is missing or invalid when a saved key must be decrypted, the app
  raises a clear `SettingsError`. It never mints a replacement key, because that
  would silently destroy access to every stored key.
- Only `api_key_last4` is stored in plain text, for the mask
  (`sk-or-...ab12`). The raw key is never written to `providers.json`, returned
  by the API, rendered into the page, or included in an error message.
- Provider errors are sanitized: if upstream text contains the key it is replaced
  with `[redacted]`, whitespace-collapsed, and truncated to 300 characters.
- `data/settings/` is gitignored, like the rest of `data/`.
- `.env` is gitignored. No secret is logged. Startup prints the bind address,
  mode, provider name, model, publisher, and debug flag only.
- `IMGBB_API_KEY` and `CONTENT_STUDIO_TOKEN` still come from `.env` or the
  environment.

## Known limitations

- **Plain HTTP.** There is no TLS. Use a reverse proxy that terminates TLS if the
  app is reachable from another machine.
- **One shared token.** There are no user accounts, roles, or per-item
  permissions. Rotate `CONTENT_STUDIO_TOKEN` and restart to revoke access.
- **No rate limiting.** The app is single-user; a public deployment would need a
  proxy-level limiter.
- **Development server.** `app.run()` is Werkzeug's server. A production
  deployment needs a WSGI server (waitress/gunicorn) in front of
  `dashboard.app:app`.
- **Publishing is mock.** No Instagram/Meta credentials are used or stored.
  `CONTENT_STUDIO_PUBLISHER` accepts only `mock`, which writes a local JSON
  package to `data/published/`; any other value makes the publish action return
  `400` and leaves the item unpublished.
- **No upload surface.** The app never accepts file uploads, so there is no
  upload-sized denial-of-service path.

## Reporting

This is a local project without a security contact. If you find an issue, open it
in the repository issue tracker with reproduction steps; do not include live
tokens or `data/state.json` contents.

## Verification

```
.\.venv\Scripts\python.exe -m pytest tests\test_security.py tests\test_settings.py tests\test_providers.py -q
```

Expected: `60 passed` for the settings/provider files plus `16 passed` for
`test_security.py`. The full fast suite is `144 passed, 3 deselected`, and the
browser suite (`pytest -m e2e`) is `3 passed`.
