# Audit result

**Date:** 2026-10-29
**Repository:** `D:\content_studio\content_studio`
**Scope:** the Flask + Pillow + JSON-file content pipeline and its browser UI, from
a clean idea to a published package, in phases 0–7.

## Summary

The pipeline now works end to end through the browser in mock mode: a topic can
be created, ideas generated, an idea selected, copy approved, assets rendered,
design approved, and the item published locally without a failed API request or
a console error.

The audit found and fixed defects in four areas:

1. **Broken control flow** — import-time LLM calls, dead approval buttons, an
   undefined `formatMap`, an action name the server did not accept, and a
   collapsed slide panel (Phase 1).
2. **Format and data corruption** — every format produced carousel copy,
   placeholder folders were shared, text files had literal `\n`, previews 404ed,
   the publish snapshot was stale, and concurrent saves crashed on Windows
   (Phase 2), followed by id collisions, ambiguous idea matching, and orphan
   artifacts (Phase 3).
3. **Unsafe defaults** — debug mode always on, no auth, no explicit CSRF check,
   and untested traversal protection (Phase 4).
4. **Silent publishing and missing coverage** — a "Publish" button that only
   wrote a local file with no configuration seam or refusal path (Phase 6), and
   no renderer/API/browser tests to keep any of this fixed (Phase 5).

Phase 7 adds the architecture, API, data, testing, integration, and audit
documents, plus a fresh-clone acceptance run.

## Method

- Each defect was reproduced before the fix; the reproduction is recorded in
  `docs/PROGRESS.md` under its phase.
- Fixes are scoped to the phase; unrelated refactors were avoided.
- `data/` was backed up before the first change
  (`data/_backup_20261029_092442/`) and before orphan cleanup
  (`data/_backup_20261029_phase3/`). Nothing was deleted.
- Every phase ended with the test suite, a commit, and a progress entry.
- Browser acceptance used the real server and the real UI, not a mocked client.

## Findings

### Phase 1 — critical control-flow bugs

| # | Severity | Finding | Reproduction | Resolution |
|---|---|---|---|---|
| 1.1 | Critical | `core/llm.py` called `requests.post` at import time using a function-local `prompt` | `OPENROUTER_API_KEY=dummy python -c "import core.llm"` → `NameError` | Moved the call into `_real_generate(prompt)`; `generate()` calls it only in live mode. |
| 1.2 | Critical | Dynamically rendered approval buttons had no listener | Clicking an `approve-btn` produced no request and left its state unchanged | Event delegation on `#approval-list`. |
| 1.3 | Critical | `formatMap` was used out of scope; a second render destroyed `#approval-empty` | `renderApproval()` → `ReferenceError`; second `loadState()` → `TypeError` on `null.style` | Hoisted the map; moved the empty node outside the list; per-item `try/catch`. |
| 1.4 | High | UI sent `approve_idea_review`, server rejected it | `POST /api/action/4` → `400 unknown action` | One `STAGE_ACTIONS` vocabulary; stage-specific buttons. |
| 1.5 | High | Slide text panel was 30 px wide instead of ~970 px | Pixel sampling at `y=500`: panel ended at `x≈85`, text started at `x=95` | Panel rectangle changed to `(55, 70, 1025, 1110)`. |

### Phase 2 — format and rendering bugs

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 2.1 | Critical | Mock Vera routed on the word "caption", so every format returned carousel copy | Route on `OUTPUT FORMAT - <FORMAT>`; one mock block per format. |
| 2.2 | High | TEXT_POST and STORY_POLL wrote to shared `item_placeholder` / `item_pending` folders | Per-item folder `data/renders/item_<id>/`. |
| 2.3 | High | Text artifacts contained literal `\n` | Real newlines when writing text. |
| 2.4 | High | Activity entries never appeared (server `time`/`message` vs UI `timestamp`/`text`) | UI reads `time`/`message`. |
| 2.5 | High | Publish snapshot recorded the pre-publish stage | Orin runs after the item reaches `done`. |
| 2.6 | High | Vera/renderer field mismatch; REEL scenes were strings | Canonical schema in `core/models.py`; normalize at both boundaries. |
| 2.7 | Medium | `run.py` printed the wrong template/static folders | Correct `BASE_DIR`. |
| 2.8 | Critical | Every preview 404ed because absolute Windows paths were served under `static/assets` | Project-relative paths plus an allowlisted `/api/asset` route. |
| 2.9 | High | Concurrent `POST /api/idea` and `/api/state` caused `PermissionError` on `os.replace` | Save lock plus bounded `os.replace` retry. |
| 2.10 | Medium | Notification/search handlers referenced an out-of-scope `state` | Module-level `lastState`. |

### Phase 3 — data integrity and cleanup

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 3.1 | Medium | Ten duplicated CSS selectors; cascade decided layout | Removed duplicates, kept one authoritative block. |
| 3.2 | Low | Purple accents remained in a green-theme UI | Converted to theme tokens. |
| 3.3 | Low | Disabled sidebar items still alerted and stole the active state | `nav-disabled` / `aria-disabled`; no navigation. |
| 3.4 | Medium | 17 orphan render artifacts and placeholder folders | Moved to `data/_backup_20261029_phase3/` with `MANIFEST.json`. |
| 3.5 | High | `id = len(items) + 1` could reuse an existing id | `max(id) + 1`. |
| 3.6 | High | Unvalidated bodies; substring idea matching could select the wrong format | JSON validation, 300-char cap, exact then case-insensitive exact match, format allowlist, render-failure `400`. |

### Phase 4 — security

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 4.1 | Critical | `debug=True` always, exposing the Werkzeug console | Debug off by default and opt-in only via `CONTENT_STUDIO_DEBUG`. |
| 4.2 | High | No authentication surface and hardcoded bind | Env-driven host/port; token required for non-loopback; startup refusal with exit 2. |
| 4.3 | Medium | CSRF protection was incidental | JSON content-type plus `Origin` / `Sec-Fetch-Site` checks. |
| 4.4 | Medium | Traversal behavior was untested | 16 security tests covering six payloads, auth, cookies, headers, and origin rules. |

### Phase 5 — test and renderer gaps

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 5.1 | High | Only the first idea could be selected: rows were `<div>`s and radios were `display:none` with no label | Rows are `<label>` elements; radios are visually hidden but focusable; checked dot and row highlight. |
| 5.2 | Medium | REEL scene cards used the 1080×1350 feed canvas | 1080×1920 vertical canvas. |
| 5.3 | High | No isolation seam, so tests could only use the real pipeline | `CONTENT_STUDIO_DATA_DIR` across state, Kite, Orin, and `/api/asset`. |
| 5.4 | High | No renderer/API/browser regression suite | 83 fast tests plus one Playwright e2e. |

### Phase 6 — publisher safety

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 6.1 | High | No publisher abstraction; Orin unconditionally wrote a local file | `describe()` / `run()` / `PublishError` in `agents/orin.py`. |
| 6.2 | High | No configuration switch or refusal path; a future mode would silently keep "publishing" locally | `CONTENT_STUDIO_PUBLISHER`, default `mock`, all other modes refused before saving. |
| 6.3 | Medium | UI said "Publish" and implied a real post | "Publish locally" plus a note naming `data/published/`. |

## Acceptance criteria

| Requirement | Status | Evidence |
|---|---|---|
| Phase 1: fresh idea → published via browser only, mock, no 400s, no console errors | Pass | Item 8 walked through every gate in a clean browser session; all `/api/` responses 200; console empty. |
| Phase 2: all 7 formats produce their own mock output, folder, and previews | Pass | Items 9–15, one per format, own `item_<id>` folder, previews loaded (REEL preview at the then-current 1350 canvas; fixed to 1920 in Phase 5). |
| Phase 3: data integrity and cleanup | Pass | Max+1 ids, lock, validation, exact selection, 17 orphans moved with manifest. |
| Phase 4: debug off, localhost bind, token, CSRF, traversal tests, `SECURITY.md` | Pass | Live probes, token instance, 16 security tests, documented limitations. |
| Phase 5: renderer/API/e2e tests and artifacts | Pass | 11 renderer, 17 API, 1 e2e; artifacts under `tests/artifacts/`; both commands green. |
| Phase 6: mock publisher default, no real Meta Graph publishing | Pass | 7 publisher tests; non-mock modes return `400` with no state change. |
| Phase 7: six docs and cross-links | Pass | `ARCHITECTURE.md`, `API.md`, `DATABASE.md`, `TESTING.md`, `INTEGRATIONS.md`, `AUDIT_RESULT.md`, plus updated `README.md`. |
| Final: fresh clone → `SETUP.md` → `python run.py` → full e2e | Pass | See "Fresh-clone acceptance" below. |
| Both test commands green | Pass | `83 passed, 1 deselected`; `1 passed, 83 deselected`. |

## Verification evidence

- `pytest -q` → `83 passed, 1 deselected in 224.67s`.
- `pytest -m e2e` → `1 passed, 83 deselected in 20.36s`.
- E2E artifacts: `e2e_carousel_design.png`, `e2e_story_poll_design.png`,
  `e2e_dashboard.png`, `e2e_server.log` (gitignored).
- Real state after the e2e run contains no `E2E` topic; the temporary server
  wrote only under its `CONTENT_STUDIO_DATA_DIR`.
- Security probes (Phase 4): traversal payloads returned `400`/`404`, form posts
  `415`, cross-origin JSON `403`, and token mode `401` without a token / `200`
  with one.
- Live UI acceptance (Phase 1–3) used the real Chromium page, not the Flask test
  client.

## Commits

| Commit | Phase |
|---|---|
| `0205759` | Baseline snapshot before audit fixes |
| `47c3c50` | Phase 0: baseline, pinned dependencies, smoke tests, docs |
| `73cecad` | Phase 1: real LLM mode, approval actions, `formatMap`, slide panel |
| `837f738` | Phase 2: canonical copy, own render folders, working previews |
| `725613d` | Phase 3: state integrity, validation, workspace cleanup |
| `51beb6a` | Phase 4: secure defaults, token auth, CSRF, headers |
| `7ba12ce` | Phase 5: renderer/API tests, Playwright e2e, data-dir isolation |
| `e19a4d0` | Phase 6: mock-only publisher, refuse real Meta Graph publishing |
| `7eac40d` | Phase 7: documentation; the fresh-clone acceptance is recorded in the follow-up docs commit |

## Residual risks and open items

These are known, documented, and intentionally not fixed in this audit. None
blocks the supported local workflow.

1. **JSON store is single-writer.** Whole-document rewrites, an in-process lock
   only, and a corrupt file silently becomes an empty store. Fine for one
   operator; move to SQLite/Postgres before multiple processes or users.
2. **Item 4 is parked at `copy`.** Left from manual testing. It is visible in the
   dashboard and can be completed or ignored; no data is lost.
3. **Pre-Phase-5 REEL assets are 1350 tall.** Only new renders use 1080×1920.
   Downstream code must read actual image sizes (D-020).
4. **Atlas live-mode failures are uncaught.** A network or OpenRouter error on
   Generate Ideas returns `500` and leaves the item unchanged. Vera failures
   degrade to fallback copy.
5. **imgbb failures are uncaught.** With `IMGBB_API_KEY` set, an upload error
   produces a `500` after the local file is written. Unset the key for a
   local-only run.
6. **`reject` at the `idea` stage** regenerates ideas but leaves the stage at
   `idea`, so the primary button is still Generate Ideas. This is a UX quirk,
   not a data bug; clicking Generate Ideas again reaches `idea_review`.
7. **No pagination on `/api/state`.** The whole store is returned on every poll.
   Fine at 16 items; a large archive would need filtering.
8. **Development server, plain HTTP.** No TLS, no WSGI server, one shared token,
   no rate limiting, CSP allows inline script/style. Intended for localhost; see
   `docs/SECURITY.md` before exposing it.
9. **Scratch files from the baseline are still tracked.** `add_css.js`,
   `check_api.js`, `fix_style.js`, `fix_style2.js`, `test_workflow.py`, and
   `core/llm.py.tmp` are unused one-off artifacts committed in `0205759`. They
   are harmless but should be removed in a separate, operator-approved cleanup.
10. **Two orphan publish snapshots.** `data/published/item_18.json` and
    `item_19.json` have no matching state item. Retained under the
    back-up-don't-delete rule.
11. **No live integration tests.** OpenRouter, imgbb, and Meta Graph are not
    exercised against real services. The mock path is the tested path.
12. **No delete/undo.** There is no API to remove an item; manual file edits need
    a backup and a stopped server.

## Fresh-clone acceptance

Run on 2026-10-29 from commit `7eac40d` (the Phase 7 documentation commit).

Clone and setup:

```powershell
git clone D:\content_studio\content_studio C:\Users\Admin\AppData\Local\Temp\opencode\cs_clone_20261029
cd C:\Users\Admin\AppData\Local\Temp\opencode\cs_clone_20261029
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

The clone contained only `data/.gitkeep`; no state, renders, backups, artifacts,
or `.env` were copied.

Install result: `flask 3.1.3`, `requests 2.34.2`, `Pillow 12.3.0`, `pytest 9.2.0`,
`playwright 1.64.1`, installed cleanly (with their transitive dependencies).

Run and manual UI:

```powershell
$env:CONTENT_STUDIO_PORT = "8091"
.\.venv\Scripts\python.exe run.py
```

Startup printed `Mode = mock`, `Publisher = mock`, `Debug = False`, and the
correct template/static directories. `GET /` returned `200` (45,196 bytes).

A Playwright session then used only the UI to create `Fresh clone acceptance`,
generate ideas, select one, approve copy, approve design, and publish:

- item 1: `stage=done`, `status=published_local`, `published=true`,
  `publish.mode=mock`, `format=CAROUSEL`
- three previews at 1080×1350
- `data/published/item_1.json` written
- console errors: none; page errors: none; `/api/` responses ≥ 400: none
- the only dialog was the expected "Idea generated" confirmation

Automated suites in the same clone:

| Command | Result |
|---|---|
| `pytest -q` | `83 passed, 1 deselected in 256.15s` |
| `pytest -m e2e` | `1 passed, 83 deselected in 19.08s` |

The e2e run wrote `e2e_carousel_design.png`, `e2e_story_poll_design.png`,
`e2e_dashboard.png`, and `e2e_server.log` to the clone's
`tests/artifacts/`. Afterwards the clone state held only the manually published
item, and the original repository's `data/state.json` still held its 16 items
with no `Fresh clone` topic.

The acceptance server was stopped; port 8091 was released.

**Result: pass.**
