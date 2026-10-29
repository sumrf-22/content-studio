# Progress

## Phase 0 — Baseline (2026-10-29)

**Status:** complete.

### Decisions
- Git root is `D:\content_studio\content_studio` (D-001).
- Reused the existing Python 3.14.6 `.venv` after verifying installs (D-002).
- Pinned the three installed runtime versions and added `pytest==9.2.0` (D-003).
- Used a repository-local git identity because none was configured (D-004).
- Backed up `data/` before any change (D-005).
- Left `data/` untracked for now (D-006).

### Changes
- `git init -b main`; baseline commit `0205759` with 24 tracked files.
- `data/_backup_20261029_092442/` created (49 files, `state.json` hash verified).
- `requirements.txt` pinned; `pytest 9.2.0` installed.
- `pytest.ini` added (`pythonpath = .`, `testpaths = tests`, `e2e` marker).
- `tests/test_smoke.py` added (dashboard 200 + state shape).
- `docs/SETUP.md`, `docs/DECISIONS.md`, this file added.

### Verification
- `pip install -r requirements.txt`: success, all runtime packages already satisfied.
- `python run.py`: server started on `127.0.0.1:8080`, `GET /` = 200 (38,706 bytes,
  title `Content Studio - Dashboard`), `GET /api/state` = 200 with 5 items and
  20 activity entries. Server stopped afterwards.
- `pytest -q`: `2 passed in 0.91s`.
- Baseline observed issues already known from the audit: wrong `run.py` debug paths,
  debug mode on, no `.env`, 3 empty render folders, literal `\n` in text artifacts.

### Blockers
- None for Phase 1.

### Open questions (needed before Phase 4/6)
- Default OpenRouter model.
- Instagram publishing: real Meta Graph integration or mock only.
- Deployment scope: localhost only or server exposure.

### Next steps
- Phase 1: reproduce the five critical bugs, then fix the LLM real-mode path, the
  approval event handling, the scoped `formatMap`, the action vocabulary /
  `select_idea`, and the slide panel geometry; regenerate affected renders.
