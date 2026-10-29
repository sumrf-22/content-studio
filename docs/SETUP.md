# Setup

## Project location

The code lives in the inner project directory:

```
D:\content_studio\content_studio
```

`D:\content_studio` is only a container folder; the git repository and all source,
tests and docs live in `D:\content_studio\content_studio`.

## Verified environment (baseline, 2026-10-29)

| Item | Value |
|---|---|
| OS | Microsoft Windows 11 Pro, version 10.0.22621, 64-bit |
| Python | 3.14.6 (`C:\Python314\python.exe`) |
| Virtualenv | `D:\content_studio\content_studio\.venv` (Python 3.14.6) |
| pip | 26.1.2 (bundled; an update to 26.2.2 is available but was not applied) |
| Git | 2.55.0.windows.3 |
| Shell | PowerShell 7+ (`pwsh`) |

## Dependencies

`requirements.txt` is pinned to the versions verified in the existing venv:

| Package | Version | Notes |
|---|---|---|
| flask | 3.1.3 | Installed and verified in the baseline venv |
| requests | 2.34.2 | Installed and verified in the baseline venv |
| Pillow | 12.3.0 | Installed and verified in the baseline venv |
| pytest | 9.2.0 | Added in Phase 0; requires Python >= 3.10 |
| playwright | 1.64.1 | Added in Phase 5 for the browser e2e suite |

`pytest` was added in Phase 0. The other runtime pins match what was already
installed, so the baseline behaviour is unchanged. New dependencies added in
later phases must be pinned here as well.

Playwright also needs a browser binary once per machine:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Install

From `D:\content_studio\content_studio`:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The repository already contained a working `.venv` with Python 3.14.6, so Phase 0
reused it after verifying `pip install -r requirements.txt` succeeds. Recreating it
is safe because `.venv/` is gitignored.

## Run

```powershell
.\.venv\Scripts\python.exe run.py
```

Open <http://127.0.0.1:8080>.

Without an OpenRouter key the app runs in mock mode. At baseline there was no
`.env` file and `OPENROUTER_API_KEY` was unset, so `MOCK_MODE` was true.

### Runtime settings

| Variable | Default | Notes |
|---|---|---|
| `CONTENT_STUDIO_HOST` | `127.0.0.1` | Non-loopback values require a token. |
| `CONTENT_STUDIO_PORT` | `8080` | |
| `CONTENT_STUDIO_DEBUG` | off | Enables the reloader and the Werkzeug debugger. |
| `CONTENT_STUDIO_TOKEN` | unset | Shared secret required for non-localhost access. |
| `CONTENT_STUDIO_DATA_DIR` | `<project>/data` | Overrides the state, render, and publish root. Must be set before start. |
| `CONTENT_STUDIO_PUBLISHER` | `mock` | `mock` saves a local package; any other value is refused. |
| `OPENROUTER_API_KEY` | unset | Empty means mock mode. |
| `OPENROUTER_MODEL` | `openrouter/free` | Free routing only. |

Example for a trusted LAN, with debug still off:

```powershell
$env:CONTENT_STUDIO_HOST = "0.0.0.0"
$env:CONTENT_STUDIO_TOKEN = "<long-random-secret>"
.\.venv\Scripts\python.exe run.py
```

Then open `http://<host>:8080/?token=<long-random-secret>` once to set the
access cookie. See `docs/SECURITY.md`.

### Baseline run evidence

- `GET /` returned HTTP 200 (38,706 bytes), title `Content Studio - Dashboard`.
- `GET /api/state` returned HTTP 200 with `items=5`, `activity=20`.
- The server started on `127.0.0.1:8080` with `Debug mode: on` and the Werkzeug
  reloader active. `run.py` printed the wrong template/static paths
  (`D:\content_studio\templates`); this is a known bug scheduled for Phase 2.
- The server process was stopped after the check; port 8080 was left free.

Current behaviour (Phase 4): debug off by default, correct template/static
paths, and the same `127.0.0.1:8080` bind.

## Test

Fast suite (renderer, API, security, state):

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Browser end-to-end suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -m e2e
```

Current results: `83 passed, 1 deselected` for the fast suite and `1 passed, 83
deselected` for e2e. The e2e run starts a real `run.py` on a free port against a
temporary data directory and writes screenshots plus `e2e_server.log` to
`tests/artifacts/` (gitignored). The operator's `data/` is never touched.

`pytest.ini` sets `pythonpath = .` so tests can import `dashboard.app` from the
project root, and `addopts = -m "not e2e"` keeps the default run browser-free.

## Data safety

Before any fix, `data/` was copied to:

```
data\_backup_20261029_092442\
```

All 49 files were copied and `state.json` matched the original SHA-256. Backups
live under `data/` and are gitignored (`data/_backup_*/`).

Phase 3 moved 17 orphan render artifacts into
`data\_backup_20261029_phase3\` (with `MANIFEST.json`). Nothing was deleted.
