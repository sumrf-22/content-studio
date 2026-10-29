# Content Studio

Local-first Instagram content pipeline with human approval gates.

```
Atlas (ideas) -> review -> Vera (copy) -> review -> Kite (design) -> review -> Orin (publish)
```

Rendering is real (Pillow). Publishing is a local package: no Instagram/Meta
credentials are used, and any publisher mode other than `mock` is refused.

## Quick start (Windows)

From this directory:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe run.py
```

Open <http://127.0.0.1:8080>.

Without an `OPENROUTER_API_KEY` the app runs in mock mode, so the full pipeline
can be exercised offline. Create a topic and click through Generate Ideas →
Use Selected Idea → Approve Copy → Approve Design → Publish locally.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest          # 83 fast tests
.\.venv\Scripts\python.exe -m pytest -m e2e   # 1 real-browser test
```

## Documentation

| Document | Contents |
|---|---|
| [docs/SETUP.md](docs/SETUP.md) | Install, run, environment variables, data safety |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Modules, request flow, stage machine, rendering |
| [docs/API.md](docs/API.md) | Endpoints, payloads, status codes, examples |
| [docs/DATABASE.md](docs/DATABASE.md) | JSON schema, file layout, invariants, backups |
| [docs/TESTING.md](docs/TESTING.md) | Test commands, fixtures, e2e, coverage gaps |
| [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) | OpenRouter, imgbb, mock publisher, future Meta Graph work |
| [docs/SECURITY.md](docs/SECURITY.md) | Deployment model, controls, limitations |
| [docs/PROGRESS.md](docs/PROGRESS.md) | Phase-by-phase audit log |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Architecture decision record (D-001…D-021) |
| [docs/AUDIT_RESULT.md](docs/AUDIT_RESULT.md) | Findings, resolutions, residual risks |

## Project location

The repository root is `D:\content_studio\content_studio`; `D:\content_studio` is
only a container folder. The default data directory is `<root>\data` and can be
moved with `CONTENT_STUDIO_DATA_DIR`.
