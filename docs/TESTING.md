# Testing

The suite has two layers: a fast, in-process suite that runs by default, and one
real-browser end-to-end test that is opt-in.

## Commands

From `D:\content_studio\content_studio`:

```powershell
# Fast suite (renderer, API, security, state, publisher)
.\.venv\Scripts\python.exe -m pytest

# One file or one test
.\.venv\Scripts\python.exe -m pytest tests\test_api.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_renderer.py::test_carousel_renders_one_slide_per_copy_slide -q

# Browser end-to-end suite
.\.venv\Scripts\python.exe -m pytest -m e2e

# Select only the fast tests explicitly
.\.venv\Scripts\python.exe -m pytest -m "not e2e"
```

`pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
addopts = -m "not e2e"
markers =
    e2e: browser end-to-end tests (requires Playwright and a running app)
```

`pythonpath = .` lets tests import `dashboard.app`, `core.*`, and `agents.*`
from the project root. `addopts` excludes e2e from the default run so a normal
`pytest` does not need a browser.

Current results (2026-10-29, Phase 6 code):

| Command | Result |
|---|---|
| `pytest -q` | `83 passed, 1 deselected in 224.67s` |
| `pytest -m e2e` | `1 passed, 83 deselected in 20.36s` |

## Test layout

| File | Tests | Focus |
|---|---|---|
| `tests/conftest.py` | — | Fixtures: isolated data root and mock LLM. |
| `tests/test_smoke.py` | 2 | Dashboard renders; `/api/state` shape. |
| `tests/test_phase1.py` | 5 | Real-mode call timing, stage/action vocabulary, `select_idea`, slide panel geometry. |
| `tests/test_phase2.py` | 18 | One idea per format, canonical Vera shape per format, per-format render folder/assets, no placeholder folders, relative paths, mixed-case parser. |
| `tests/test_phase3.py` | 7 | Id collisions, concurrent creates, missing/overlong topic, exact title selection, unknown format fallback. |
| `tests/test_renderer.py` | 11 | Canvas size and PNG output per format, slide counts, REEL scene cards/scripts, real newlines, invalid copy, item folder. |
| `tests/test_api.py` | 17 | Full pipeline through Flask, all seven formats, rejection paths, render rollback, post-publish lockout, text assets. |
| `tests/test_security.py` | 16 | Asset allowlist/traversal, headers, form and cross-origin rejection, token auth and cookie flow. |
| `tests/test_publisher.py` | 7 | Mock default, package contents, refusal of `instagram`/`meta`/`graph`/`live`, no state change on refusal. |
| `tests/e2e/test_ui_pipeline.py` | 1 | Real server, real Chromium, two formats from create to published. |

Parametrization explains why the file counts are higher than the number of test
functions: the seven-format renderer/API tests and the four refused publisher
modes each expand into separate cases.

## Fixtures

### `isolated_data`

Redirects every storage path at a pytest `tmp_path`:

```python
monkeypatch.setattr(state_module, "DATA", data)
monkeypatch.setattr(state_module, "STATE", data / "state.json")
monkeypatch.setattr(app_module, "DATA_ROOT", data)
monkeypatch.setattr(kite, "DATA_ROOT", data)
monkeypatch.setattr(kite, "RENDER_DIR", data / "renders")
monkeypatch.setattr(orin, "DATA", data)
```

Any test that writes state, renders, publishes, or fetches `/api/asset` must
request this fixture. It is not autouse because pure parser/canvas tests do not
need it, but asking for it is always safe.

### `mock_llm` (autouse)

Every test forces `core.llm.MOCK_MODE = True`, so a developer's local
`OPENROUTER_API_KEY` can never turn a test into a live network call. The e2e
subprocess removes the key from its environment for the same reason.

### Local fixtures

- `tests/test_phase3.py`: `temp_state` and `client` for id and endpoint tests.
- `tests/test_security.py`: `project_root`, `client`, `token`.
- `tests/test_renderer.py`: `render_dir` alias over `isolated_data`.
- `tests/test_api.py` / `test_publisher.py`: `client` over `isolated_data`.

## What the fast suite guarantees

- **State:** ids never collide; concurrent creates all land; saves survive
  Windows replace contention; the documented `{items, activity}` shape holds.
- **Copy:** each format has its canonical shape; Vera returns it in mock mode;
  unknown formats fall back to CAROUSEL.
- **Rendering:** each of the seven formats writes into its own
  `renders/item_<id>/` folder; image formats have the documented canvas size and
  PNG magic; REEL gets a card and a script per scene; TEXT_POST has real
  newlines and no image.
- **API contract:** the exact browser sequence works end to end; illegal stage
  actions, missing items, unknown actions, missing idea titles, failed renders,
  and post-publish actions are all rejected with the right status; publish
  writes the final snapshot.
- **Security:** traversal payloads are refused; the state file is not served;
  headers are present; form/cross-origin/cross-site mutations are refused; token
  mode accepts header, cookie, and query flows.
- **Publisher:** mock is the only accepted mode; refusal changes nothing.

## Browser e2e

`tests/e2e/test_ui_pipeline.py` is a single test marked `e2e`.

What it does:

1. Picks a free port and a temporary data directory.
2. Starts the real `run.py` as a subprocess with
   `CONTENT_STUDIO_DATA_DIR=<tmp>`, `CONTENT_STUDIO_HOST=127.0.0.1`, and the
   OpenRouter/token/debug variables removed.
3. Waits for `/api/state` to answer, then launches Chromium with Playwright.
4. For CAROUSEL and STORY_POLL, clicks through the UI only:
   topic → Generate Ideas → select an idea row → Use Selected Idea →
   Approve Copy → check preview dimensions → Approve Design → Publish locally.
5. Asserts the item is `done` / `published_local` / `published=true` and that
   the publish snapshot records `mode=mock`.
6. Records any console error, page error, or `/api/` response ≥ 400 and fails if
   any occurred.

Artifacts land in `tests/artifacts/` (gitignored):

- `e2e_carousel_design.png`
- `e2e_story_poll_design.png`
- `e2e_dashboard.png`
- `e2e_server.log`

Because the server is pointed at a temporary directory, the operator's real
`data/` is never used; the published snapshot is checked inside the temporary
directory.

Requirements: `playwright==1.64.1` plus a browser binary.

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

### Why only two formats in e2e

The renderer and API suites already cover all seven formats deterministically.
The browser test exists to catch integration bugs that unit tests miss: event
delegation, hidden controls, asset URLs, and response handling. CAROUSEL
exercises a multi-image flow and STORY_POLL exercises the 1080×1920 flow and the
`frames` design shape. Repeating all seven would add minutes without new
coverage; add a format here only if its UI path differs structurally.

## Manual browser acceptance

Automation cannot judge whether the dashboard looks right. Before a release:

1. Start `python run.py` and open `http://127.0.0.1:8080`.
2. Open DevTools, clear the console, and enable "Preserve log".
3. Create a topic, then click each gate in order for at least one image format
   and TEXT_POST.
4. At the design stage confirm previews load (not broken images) and that the
   canvas matches the format table in `docs/ARCHITECTURE.md`.
5. Publish and confirm the card leaves the approval queue, the recent-content
   list updates, and the activity log shows the publisher.
6. Reload and confirm state persisted.
7. Check the console has no errors and every `/api/` response is < 400.

The same checklist was used for the Phase 1, 2, and 3 acceptances.

## Adding tests

- Prefer the API-level test in `tests/test_api.py` for a new stage/action rule.
- Add a renderer case in `tests/test_renderer.py` when asset shape or canvas
  changes; extend `CANVAS` and the format list.
- Add a security case to `tests/test_security.py` for any new route that reads
  a path or accepts a body.
- Use `isolated_data`; never point a test at the real `data/`.
- Keep deterministic tests in the default suite. Only browser tests get the
  `e2e` marker.
- When a bug is fixed, add the failing case first and record the pre-fix
  reproduction in `docs/PROGRESS.md`.

## Coverage gaps

- No test makes a real OpenRouter request. The live path is exercised with a
  monkeypatched `requests.post` in `test_phase1.py`.
- Atlas live-mode errors are not tested because the code does not catch them;
  they surface as `500`.
- imgbb upload success/failure is not tested (there is no key in CI).
- Token mode is tested in-process, not through the Playwright server.
- No load, concurrency, or long-running soak test; the app is single-operator.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `playwright` cannot launch Chromium | Run `python -m playwright install chromium`. |
| e2e fails with "server did not start" | Read `tests/artifacts/e2e_server.log`; usually a port conflict, an import error, or a stale process. |
| Tests write to the real `data/` | A test forgot `isolated_data`; fix the test, then restore from a backup if needed. |
| Fast suite is slow | Rendering seven formats with Pillow is the cost; use a file or `-k` filter while iterating. |
| `PermissionError` on `state.json` | Another process holds the file. Stop the dev server before manual edits; the app itself retries for 1 s. |
