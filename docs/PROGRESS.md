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

## Phase 1 — Critical bugs (2026-10-29)

**Status:** complete.

### Reproductions (recorded before fixing)

1. **LLM import-time call** — `OPENROUTER_API_KEY=dummy python -c "import core.llm"`
   raised `NameError: name 'prompt' is not defined` at `core/llm.py:164`. The
   module-level `requests.post` referenced the inside-function `prompt`.
2. **Dynamic approval buttons** — on the loaded dashboard,
   `document.querySelector('.approve-btn[data-item-id="4"]').click()` produced no
   network request and left the button text/disabled state unchanged. The
   `querySelectorAll` listener registration runs before `renderApproval()`'s
   async state fetch creates the buttons.
3. **Scoped `formatMap`** — after creating an `idea_review` item with ideas,
   `renderApproval()` threw `ReferenceError: formatMap is not defined`. A second
   `loadState()` also exposed `TypeError: Cannot read properties of null
   (reading 'style')` because the first successful render replaced
   `#approval-empty` via `innerHTML`.
4. **Invalid action vocabulary** — the approval button carried
   `data-action="approve_idea_review"`. Posting that action to
   `/api/action/4` returned `400 {"error": "unknown action"}`.
5. **Panel geometry** — rendering one slide and sampling row `y=500` showed the
   dark panel only at `x ≈ 55..85`; `x=86` and beyond were the raw background,
   while the text starts at `x=95`. The panel was 30 px wide instead of 970 px.

### Changes

- `core/llm.py`: moved the OpenRouter request into `_real_generate(prompt)`;
  `generate()` now calls it only when `MOCK_MODE` is false. Added a generic
  Atlas mock fallback so topics outside the canned keyword lists still return
  ideas and can move through the pipeline.
- `dashboard/app.py`: added `STAGE_ACTIONS`, one action vocabulary enforced on
  the server (`approve_idea`, `select_idea`, `approve_copy`, `approve_design`,
  `publish`, `reject`). Invalid or stale actions now return a descriptive 400.
  `reject` regenerates ideas at both `idea` and `idea_review`.
- `templates/index.html`: hoisted `formatMap`; moved `#approval-empty` outside
  `#approval-list`; per-item `try/catch` in `renderApproval()`; replaced the
  per-button listeners with event delegation on `#approval-list`; stage-specific
  primary buttons; added idea radio selection that sends `selected_idea`.
- `agents/kite.py`: `_render_slide` panel changed to `(55, 70, 1025, 1110)`.
- `tests/test_phase1.py`: regression tests for real-mode routing, stage/action
  validation, `select_idea`, and panel coverage.

### Verification

- Fresh browser session, item 8, mock mode, UI only:
  create idea → Generate Ideas → Use Selected Idea → Approve Copy →
  Approve Design → Publish.
- Final state: `stage=done`, `status=published_local`, `published=true`.
- Console messages: none. All `/api/` requests in that session returned 200.
- `pytest -q`: `7 passed in 5.30s`.
- Real-mode path was exercised with a monkeypatched `requests.post`: the API is
  called at `generate()` time and the returned content is used; mock mode still
  returns Atlas ideas.

### Renders regenerated

Re-rendered with the corrected panel: `item_1/slide_1`, `item_2/slide_1..5`,
`item_18/slide_1`, `item_19/slide_1`, `item_99/slide_1..2`,
`item_999/slide_1..2`, `item_100/slide_1..2`. `item_7` was rendered after the
fix. Placeholder/test-artifact text was reconstructed from the pre-fix images
because those item IDs have no matching state entries.

The stray `data/renders/item_*_slide_1.png` files at the renders root come from
an older, different renderer (black background, no panel) and were not affected.
`item_3`, `item_104`, and `item_106` contain no slide PNGs.

### Data changes

Created items 6, 7, and 8 while reproducing and validating the UI, and
regenerated item 4's ideas. The verified pre-change backup remains at
`data/_backup_20261029_092442/`.

### Blockers
- None.

### Next steps
- Phase 2: mock format routing, per-item folders, real newlines, activity field
  names, Orin snapshot ordering, Vera/renderer schema alignment, `run.py` paths,
  and preview/asset serving.

## Phase 2 — Formats and rendering (2026-10-29)

**Status:** complete.

### Reproductions (recorded before fixing)

1. **Mock format routing ignored the selected format.** Asking for
   `REEL`/`SINGLE_IMAGE`/`MEME` returned the same carousel text, so Vera produced
   carousel-shaped copy for every format. The mock matched the word "caption",
   which appears in every Vera prompt.
2. **Placeholder output folders.** `TEXT_POST` wrote into
   `data/renders/item_placeholder/text_post.txt` and `STORY_POLL` wrote frames
   into `data/renders/item_pending/`, so two items shared one folder and the item
   ID never appeared in the path.
3. **Literal `\n` in text artifacts.** `data/renders/.../text_post.txt` contained
   `HOOK: ...\n\nPOST_TEXT: ...` on one line instead of real line breaks.
4. **Activity entries never rendered.** `/api/state` returned
   `{"time", "message"}`, while the dashboard read `act.timestamp`/`act.text`, so
   every row showed "Just now" with an empty message.
5. **Publish snapshot was stale.** `orin()` ran before the item moved to
   `done`/`published_local`, so `data/published/item_<id>.json` recorded the
   pre-publish stage.
6. **Vera/renderer field mismatch.** Vera returned `visual_direction` while
   Kite's dict path expected other names; `REEL` raised
   `AttributeError: 'str' object has no attribute 'get'` because scenes were
   strings, not dicts.
7. **`run.py` printed the wrong folders.** Startup logged
   `...\content_studio\templates` for the template dir even though the real
   templates live one level deeper.
8. **No working previews.** Kite stored absolute Windows paths; `/api/asset`
   resolved everything under `static/assets/`, so every preview returned 404 and
   the design preview grid was empty.

Found during acceptance of this phase (also fixed):

9. **`POST /api/idea` 500 under concurrent reads.** Server log at 09:55:30:
   `PermissionError: [WinError 5] ... os.replace(...state.json)` raised from
   `core/state.py:49` while `/api/state` was being polled. Windows refuses the
   replace while another thread holds the destination open.
10. **`ReferenceError: state is not defined`.** Clicking the notification bell
    threw at `index.html:735`; `state` was local to `loadState()`. The search
    handler had the same defect at line 855.

### Changes

- `core/models.py` (new): one canonical copy shape per format,
  `normalize_copy()`, and `fallback_copy()`.
- `core/llm.py`: Vera's mock routes on the exact `OUTPUT FORMAT - <FORMAT>`
  string and has a block for all seven formats; Atlas' generic fallback returns
  one idea per format.
- `agents/vera.py`: section-based plain-text parser (`_sections`, `_parse_header`,
  `_parse_carousel`, `_build_copy`, `_detect_format`); output is normalized
  through `core.models` and falls back to a valid copy dict on parse failure.
- `agents/kite.py`: normalizes copy at the renderer boundary; removed the old
  `_parse_structured_copy`; per-item folders via `RENDER_DIR / f"item_{item_id}"`;
  TEXT_POST/STORY_POLL write into the item folder; real newlines; REEL scenes stay
  dicts; infographic splits on lines; asset paths stored project-relative through
  `_rel()`.
- `dashboard/app.py`: allowlisted `/api/asset` (`data/renders/`, `static/assets/`)
  with `.txt` MIME; `orin()` runs after the final state; Kite receives the copy
  dict directly; removed `_format_copy_for_kite`; activity counts use
  `len(ideas)`.
- `agents/atlas.py`: keeps up to seven ideas so every format can be selected.
- `core/state.py`: `save()` serializes writes with a lock and retries
  `os.replace` on `PermissionError` for up to 1 s.
- `run.py`: correct `BASE_DIR` for the startup log.
- `templates/index.html`: `assetUrl()`, `designFiles()`, `copySnippet()`;
  activity reads `time`/`message`; design previews render images or text for every
  format; content-card thumbnails come from the design; `lastState` backs the
  notification and search handlers.
- `static/style.css`: `.preview-carousel { width: 100% }`, `.preview-text`.
- `tests/test_phase2.py` (new): canonical shapes, one idea per format, per-format
  render folders, no placeholder folders, project-relative `_rel()`, and
  mixed-case header parsing.

### Verification

Browser session, mock mode, UI only (create → Generate Ideas → select idea →
Approve Copy), one fresh item per format:

| Item | Format | Output folder | Assets | Preview |
| --- | --- | --- | --- | --- |
| 9 | CAROUSEL | `item_9` | 3 slides | 1080×1350 loaded |
| 10 | SINGLE_IMAGE | `item_10` | 1 image | 1080×1350 loaded |
| 11 | REEL | `item_11` | 3 scene cards + 3 scene txt | 1080×1350 loaded |
| 12 | INFOGRAPHIC | `item_12` | 1 image | 1080×1350 loaded |
| 13 | TEXT_POST | `item_13` | `text_post.txt` | text preview, real newlines |
| 14 | MEME | `item_14` | 1 image | 1080×1350 loaded |
| 15 | STORY_POLL | `item_15` | 2 frames | 1080×1920 loaded |

All seven then went through Approve Design and Publish. Every item ended at
`stage=done`, `status=published_local`, `published=true`, and each
`data/published/item_<id>.json` records that final state. No
`item_placeholder`/`item_pending` folder was created. A clean page reload plus
notification and search interactions produced zero console errors, and all
captured `/api/` responses were < 400.

- `pytest -q`: `25 passed in 56.32s`.

### Data changes

Created items 9–15 (`Format sweep …`) and their render folders and publish
snapshots. Item 4 remains at `copy` from earlier manual testing. The Phase 0
backup at `data/_backup_20261029_092442/` is unchanged.

### Known leftovers (deferred)

- Legacy `data/renders/item_placeholder/` and `item_pending/` folders from before
  the fix still exist on disk; nothing writes to them now.
- Stray `data/renders/item_*_slide_1.png` files from an older renderer.
- REEL scene cards are 1080×1350 while story frames are 1080×1920. Production
  reels need 1080×1920; tracked for the renderer phase.
- Items 1/2 keep legacy flat copy dicts; normalization handles them.

### Blockers
- None.

### Next steps
- Phase 3: storage/repository work and the remaining audit issues (CSS duplicates,
  sidebar placeholders, legacy artifact cleanup).

## Phase 3 — Data integrity and cleanup (2026-10-29)

**Status:** complete.

### Scope decision

The audit plan left Phase 3 as "storage". It is delivered as **data integrity +
workspace cleanup**: the JSON store stays behind `core/state.py`, mutation
endpoints run one at a time, ids cannot collide, request bodies are validated,
the `.gitignore` now targets generated data, and the leftover audit issues
(duplicate CSS, purple-vs-green theme drift, sidebar placeholders, orphan render
artifacts) are resolved (D-014, D-015).

### Reproductions and evidence (pre-fix, commit `837f738`)

1. **Ten duplicated CSS selectors.** Counting rules in `git show
   837f738:static/style.css` returned `.approval-card`, `.approval-list`,
   `.approval-item`, `.approval-item:hover`, `.approval-head`, `.approval-badge`,
   `.approval-badge-idea`, `.approval-badge-copy`, `.approval-badge-design`, and
   `.approval-actions` twice each. The first `.approval-item` used a row layout
   and the second a column layout, so the cascade silently decided the UI.
2. **Theme drift.** Ten declarations still used the old purple accent
   `rgba(108, 92, 231, …)` while `--accent` is `#22c55e`, including sidebar hover,
   the sidebar active pill, `.btn-primary:hover`, `.preview-header`, and
   `.status-running`.
3. **Sidebar placeholders.** Every non-dashboard link ran
   `alert('Navigating to: ' + section + ' (not yet implemented)')` and still
   received the `active` class, so the UI claimed a section that does not exist.
4. **Orphan render artifacts.** `data/renders/` held two placeholder folders
   (`item_pending`, `item_placeholder`), ten `item_*` folders with no matching
   state entry (18, 19, 99, 100–106, 999), three stray root PNGs
   (`item_1_slide_1.png`, `item_2_slide_1.png`, `item_4_slide_1.png`), and
   `data/imgbb_test.png`.
5. **Id generation could collide.** `create_item()` used
   `id = len(items) + 1`; removing any item would make the next id reuse an
   existing one.
6. **Unvalidated request bodies.** `POST /api/idea` read `request.json.topic`
   directly, and `select_idea` matched the selected title by substring, so a
   partial title could resolve to the wrong format.

### Changes

- `core/state.py`: `next_id()` (max + 1), `locked()` context manager backed by an
  `RLock`, and `create_item()` holds that lock for its read-modify-write.
- `dashboard/app.py`: `action()` wraps `_handle_action()` in `locked()`;
  `_resolve_idea()` replaces substring matching with exact then case-insensitive
  exact matching and returns 400 for an unknown title; the selected format is
  validated against `core.models.SUPPORTED_FORMATS`; `_render_failed()` returns
  400 instead of storing an empty design when Kite reports a problem; topics are
  required and capped at 300 characters; `request.get_json(silent=True)` replaces
  `request.json`.
- `static/style.css`: removed the ten duplicate approval rules (kept one
  authoritative block and the shared `.btn-sm`), converted all purple accents to
  the green theme, added `.sidebar-nav a.nav-disabled`.
- `templates/index.html`: seven non-dashboard sections are marked
  `nav-disabled`/`aria-disabled` and no longer alert or steal the active state.
- `.gitignore`: narrowed from `data/` to `data/state.json`,
  `data/.state-*.tmp`, `data/renders/`, `data/published/`, `data/_backup_*/`, and
  `tests/artifacts/`; `data/.gitkeep` keeps the folder in a fresh clone.
- `tests/test_phase3.py`: id collision, 8-way concurrent create, missing/overlong
  topic, unknown selected idea, exact-vs-substring selection, unknown format
  fallback.

### Cleanup performed

`data/_backup_20261029_phase3/` now holds the 17 orphan artifacts listed above
(plus `MANIFEST.json` with the state ids that were kept). Nothing was deleted;
everything was moved out of `data/renders/` after the copy, and the verified
Phase 0 backup is untouched.

### Verification

- Browser, mock mode: created item 16 (`Phase 3 check carousel`) and ran
  create → Generate Ideas → Use Selected Idea → Approve Copy → Approve Design →
  Publish. Result: `stage=done`, `status=published_local`, 3 slides,
  preview images 1080×1350 loaded.
- Clean reload and navigation clicks: zero alerts from the sidebar, only
  `Dashboard` can become active.
- Console errors: none. All captured `/api/` responses < 400.
- `pytest -q`: `32 passed in 55.35s`.

### Data changes

Item 16 created and published. Orphan renders moved to the Phase 3 backup.
`data/state.json` remains untracked by design.

### Blockers
- None.

### Next steps
- Phase 4: security posture — `debug=False` default, bind `127.0.0.1`, token for
  non-localhost, CSRF, path-traversal tests, `docs/SECURITY.md`.

## Phase 4 — Security (2026-10-29)

**Status:** complete.

### Findings before the change (commit `725613d`)

1. **Debug mode always on.** `run.py` ended with
   `app.run(host="127.0.0.1", port=8080, debug=True)`. Startup logs from the
   Phase 2 session show the consequence: `Debugger is active! Debugger PIN:
   954-738-013`. Anyone who can reach the port can execute code through the
   Werkzeug console.
2. **No authentication surface at all.** `grep -n "token\|auth\|login"
   dashboard/app.py` matched nothing, and the host/port were hardcoded, so there
   was no supported way to expose the app and no way to protect it if someone
   changed the bind address by hand.
3. **CSRF checks were incidental, not explicit.** Mutations happened to require
   JSON (`request.get_json(silent=True)`), which a cross-site form cannot send,
   but nothing verified `Origin` or `Sec-Fetch-Site` and nothing rejected
   non-JSON bodies on purpose.
4. **Traversal behaviour was untested.** The Phase 2 allowlist existed but had no
   regression tests; a future edit could have reopened `static/assets` traversal.

### Changes

- `config.py`: `ACCESS_TOKEN` read from `CONTENT_STUDIO_TOKEN`.
- `run.py`: host/port/debug come from `CONTENT_STUDIO_HOST/PORT/DEBUG`
  (debug off by default, no reloader unless enabled). A non-loopback bind without
  a token exits with code 2 before the server starts, and a non-loopback bind
  prints a plain-HTTP warning. Startup prints the resolved dirs, mode, and debug
  flag.
- `dashboard/app.py`:
  - `guard_request()` — constant-time token check against the
    `X-Content-Studio-Token` header, the `cs_token` cookie, or a one-time
    `?token=` query that sets an `HttpOnly`, `SameSite=Strict`, `Secure`-when-HTTPS
    cookie and redirects to `/`.
  - CSRF guard — mutating requests with a body must be `application/json`, and
    `Origin` / `Sec-Fetch-Site` must match the request host when present.
  - `security_headers()` — `nosniff`, `DENY` framing, `no-referrer`, and a
    same-origin CSP.
- `tests/test_security.py`: 16 tests for token auth, cookie flow, form and
  cross-origin rejection, headers, and six traversal payloads.
- `docs/SECURITY.md`: deployment matrix, each control, limitations, verification.

### Verification

Live probes against `127.0.0.1:8080`:

| Probe | Result |
|---|---|
| `/api/asset/../state.json` | 404 (normalized, not served) |
| `/api/asset/data/renders/../../state.json` | 404 |
| `/api/asset/static/assets/../../secret.txt` | 404 |
| `/api/asset/C:/Windows/win.ini` | 400 |
| `/api/asset/%2e%2e/state.json` | 400 |
| `/api/asset/..%2Fstate.json` | 400 |
| Form-encoded `POST /api/idea` | 415 |
| JSON `POST /api/idea` with `Origin: https://evil.example` | 403 |

Token mode, separate instance on port 8099 with
`CONTENT_STUDIO_TOKEN=local-test-token`:

- `GET /api/state` without a token → 401.
- `GET /api/state` with `X-Content-Studio-Token` → 200.
- `GET /?token=…` followed by cookie auth → 200.
- `CONTENT_STUDIO_HOST=0.0.0.0` without a token → refuses to start, exit 2.

Server restarted with the new entrypoint: `Debug = False`, `Debug mode: off`,
page 200 with the CSP header, dashboard renders 8 content cards and six design
previews with zero console errors.

- `pytest -q`: `48 passed in 56.26s` (16 of them security tests).

### Data changes

None. The origin-test request was rejected before it reached `create_item()`.

### Blockers
- None.

### Next steps
- Phase 5: renderer/API/e2e Playwright tests, artifacts in `tests/artifacts/`.

## Phase 5 — Tests: renderer, API, browser e2e (2026-10-29)

**Status:** complete.

### Reproductions (recorded before fixing)

1. **Only the first idea could be selected in the browser.** The idea rows were
   `<div>`s and the radio inputs were `display:none` with no `<label>`, so
   `document.querySelectorAll('.preview-stage-row')[2].click()` left every radio
   in its original state (`[true, false, false]` stayed unchanged). A person
   could publish idea 0 and nothing else. The companion rule
   `.idea-radio input:checked + .idea-title` could never match either, because
   the input has no sibling — only the span and title after it.
2. **REEL scene cards used the feed canvas.** Phase 2 recorded 1080×1350 cards
   for a vertical video format. `agent/kite.py` hard-coded `HEIGHT` in
   `_create_vertical_scene_scene_card` even though the story renderer already
   used `HEIGHT_VERTICAL`.
3. **No isolation seam for tests.** `core/state.py`, `agents/kite.py`,
   `agents/orin.py`, and `/api/asset` each recomputed or hard-coded the `data/`
   path, so an end-to-end test could only run against the operator's real
   pipeline.

### Changes

- `core/state.py`: `DATA` honours `CONTENT_STUDIO_DATA_DIR` (defaults to
  `<project>/data`).
- `agents/kite.py`: `RENDER_DIR = DATA_ROOT / "renders"`, `_rel()` relative to
  `DATA_ROOT.parent`, and REEL scene cards now render 1080×1920.
- `agents/orin.py`: publish snapshots go to `<data>/published`.
- `dashboard/app.py`: `/api/asset` resolves `data/renders/...` under the
  configured data root.
- `templates/index.html`: idea rows are now `<label>` elements, so the whole row
  is a click and keyboard target for the hidden radio.
- `static/style.css`: focusable-but-hidden radios, a filled dot for the checked
  choice, checked-row highlight, `:focus-within` outline, and removal of the
  duplicated/dead checked-title rule.
- `tests/conftest.py` (new): `isolated_data` redirects state, renders, publish
  output and the asset root at `tmp_path`; `mock_llm` forces mock mode.
- `tests/test_renderer.py` (new, 11 tests): canvas size per format, PNG output,
  one slide per copy slide, one scene card + script per REEL scene, real
  newlines in `TEXT_POST`, invalid-copy failure shape, item folder contents.
- `tests/test_api.py` (new, 17 tests): full create → ideas → select → copy →
  design → publish pipeline with asset fetches and the final snapshot, all seven
  formats, early-publish rejection, missing item, unknown action, missing title,
  render-failure rollback, reject/regenerate, post-publish lockout, text assets.
- `tests/e2e/test_ui_pipeline.py` (new, 1 test, marked `e2e`): starts a real
  `run.py` on a free port with `CONTENT_STUDIO_DATA_DIR=<tmp>`, then clicks
  CAROUSEL and STORY_POLL through the UI, checks preview dimensions, the final
  state, console/page errors, `/api/` 4xx/5xx responses, and the publish
  snapshot.
- `pytest.ini`: `addopts = -m "not e2e"` keeps the default run fast; `-m e2e`
  selects the browser suite.
- `requirements.txt`: `playwright==1.64.1` pinned.

### Verification

- `pytest -q`: `76 passed, 1 deselected in 135.40s`.
- `pytest -m e2e`: `1 passed, 76 deselected in 22.61s`.
- The e2e run published two items in a temporary data directory. Six artifacts
  are written to `tests/artifacts/` (gitignored): carousel and story design
  screenshots, the dashboard screenshot, and `e2e_server.log`.
- Isolation checked afterwards: the real `data/state.json` contains no `E2E`
  topic and the two temp items never appear in the real render tree.
- Manual check in the real browser: rendering a synthetic three-idea review card
  and clicking the third row produced `[false, false, true]` and an 8×8 check
  dot, confirming the label fix in the shipped CSS.
- The server was restarted on the new code (`run.py`, `127.0.0.1:8080`, debug
  off).

### Data changes

None in `data/`. Test output is confined to pytest temp directories; the e2e
server log and screenshots live in the gitignored `tests/artifacts/`.

### Blockers
- None.

### Next steps
- Phase 6: make the mock publisher the explicit default and refuse real Meta
  Graph publishing until an account/app is confirmed.

## Phase 6 — Publisher safety (2026-10-29)

**Status:** complete.

### Findings before the change (commit `7ba12ce`)

1. **No publisher abstraction.** `agents/orin.py` unconditionally wrote
   `data/published/item_<id>.json` and returned
   `"Saved locally (publishing is intentionally disabled in v1)."`. The API
   ignored that return value, set `published=true`, and reported
   `published_local`. There was no configuration switch, so a future integration
   had nowhere to plug in and no way to distinguish a local package from a real
   publish.
2. **No refusal path.** `grep -ri "graph.facebook\|instagram.*api\|meta.*token"`
   found nothing, and `config.py` had no publishing setting. Adding a real
   integration would have silently changed the meaning of the Publish button.
3. **The UI overstated the action.** The final-stage button said `Publish` and
   the stage preview only said "Ready for final publish approval", with no hint
   that the step is local-only.

### Changes

- `config.py`: `PUBLISHER` from `CONTENT_STUDIO_PUBLISHER`, default `mock`,
  normalised to lowercase.
- `agents/orin.py`: `SUPPORTED_PUBLISHERS = {"mock"}`, `PublishError`,
  `describe()` returning `{"mode": "mock", "target": "local", "message": ...}`,
  and `run()` that refuses unknown modes before writing anything. The publish
  metadata is attached to the item before the snapshot is written.
- `dashboard/app.py`: the publish branch catches `PublishError` and returns
  `400` without saving, so the item stays at the `publish` stage with
  `published=false`. Successful activity logs now name the publisher.
- `templates/index.html`: final button reads `Publish locally`; the stage
  preview states that the mock publisher writes under `data/published/` and does
  not call Instagram.
- `run.py`: startup prints `Publisher = <mode>`.
- `tests/test_publisher.py` (new, 7 tests): default mode, mock package contents,
  refusal for `instagram`/`meta`/`graph`/`live`, no stage change, no snapshot,
  no activity entry on refusal.
- `tests/test_api.py` and `tests/e2e/test_ui_pipeline.py`: assert the stored
  publish metadata and the snapshot both record `mode=mock`.

### Verification

- Default (`CONTENT_STUDIO_PUBLISHER` unset): publish returns 200,
  `item.publish = {"mode": "mock", "target": "local", ...}`, the snapshot is
  written, and the activity log says `publisher: mock`.
- `CONTENT_STUDIO_PUBLISHER=instagram` (or any non-mock value): publish returns
  `400` with
  `publisher 'instagram' is not available: real Meta Graph publishing is disabled until the Instagram account and Meta app are confirmed.`
  The item remains at `publish`, `published=false`, no snapshot file is created,
  and no activity entry is added.
- `pytest -q`: `83 passed, 1 deselected in 212.25s`.
- `pytest -m e2e`: `1 passed, 83 deselected in 21.27s`.

### Data changes

None. The publisher tests use the `isolated_data` fixture, and the browser e2e
uses a temporary data directory.

### Blockers
- None. Real Instagram publishing remains intentionally unimplemented.

### Next steps
- Phase 7: architecture, API, data, testing, integration, and audit docs; then a
  fresh-clone acceptance run.

## Phase 7 — Documentation and acceptance (2026-10-29)

**Status:** complete.

### Findings before the change

1. **Four documents existed, six were missing.** `SETUP.md`, `SECURITY.md`,
   `PROGRESS.md`, and `DECISIONS.md` covered install, deployment, history, and
   decisions, but there was no architecture map, API reference, data schema,
   testing guide, integration guide, or consolidated audit result. A new
   maintainer had to read the source to learn the stage machine or the JSON
   shape.
2. **`README.md` was stale and wrong.** It told the reader to `cd
   D:\Content-Studio` — a path that does not exist — and omitted Playwright,
   the mock publisher, the test commands, and every document.
3. **`docs/SETUP.md` test counts were stale.** It still reported `76 passed` and
   `1 passed, 76 deselected` after Phase 6 raised the totals to 83 + 1.

### Changes

- `docs/ARCHITECTURE.md` (new): runtime topology, module responsibilities,
  request lifecycle, the stage/action machine, data flow, per-format rendering
  table, path model, concurrency, failure handling, security boundary, and
  extension points.
- `docs/API.md` (new): conventions, auth/CSRF rules, every endpoint, action
  contract, error matrix, status codes, and PowerShell examples.
- `docs/DATABASE.md` (new): file layout, `state.json` schema, per-format copy
  and design shapes, id allocation, atomic writes, invariants, backups,
  retention, schema evolution, and known data notes.
- `docs/TESTING.md` (new): commands, per-file coverage table, fixtures, e2e
  internals, manual checklist, conventions, gaps, and troubleshooting.
- `docs/INTEGRATIONS.md` (new): OpenRouter request/mode/failure behaviour, imgbb
  egress and failure mode, mock publishing, and the requirements for a future
  Meta Graph integration.
- `docs/AUDIT_RESULT.md` (new): findings per phase, acceptance criteria,
  verification evidence, commit list, residual risks, and fresh-clone results.
- `docs/SETUP.md`: current test counts and a pointer to the new docs.
- `README.md`: correct project path, quick start including
  `playwright install chromium`, test commands, publisher note, and a
  documentation index.

### Verification

- `pytest -q`: `83 passed, 1 deselected in 224.67s`.
- `pytest -m e2e`: `1 passed, 83 deselected in 20.36s`.
- Cross-checked every documented field, route, status code, canvas size, and
  environment variable against the current source before writing it.

### Fresh-clone acceptance

Cloned commit `7eac40d` to
`C:\Users\Admin\AppData\Local\Temp\opencode\cs_clone_20261029`, created a new
venv, installed `requirements.txt` and Chromium, and started `python run.py` on
port 8091. The clone contained only `data/.gitkeep`.

- Startup: `Mode = mock`, `Publisher = mock`, `Debug = False`, correct
  template/static paths; `GET /` returned 200 (45,196 bytes).
- UI only: created `Fresh clone acceptance`, generated ideas, selected one,
  approved copy and design, and published. Item 1 ended at `stage=done`,
  `status=published_local`, `published=true`, `publish.mode=mock`, with three
  1080×1350 previews and `data/published/item_1.json`.
- Console errors, page errors, and `/api/` responses ≥ 400: none.
- `pytest -q`: `83 passed, 1 deselected in 256.15s`.
- `pytest -m e2e`: `1 passed, 83 deselected in 19.08s`.
- The original repository's state still held its 16 items and no
  `Fresh clone` topic. The acceptance server was stopped.

**Result: pass.** Details are in `docs/AUDIT_RESULT.md`.

### Data changes

None in the original repository. Documentation only; the acceptance wrote only
to the temporary clone and its pytest temp directories.

### Blockers
- None.

### Next steps
- None. The audit plan (phases 0–7) is complete.

## Post-audit Task 1 — "View All" label (2026-10-29)

**Status:** complete.

### Reproduction (recorded before fixing)

1. Started `run.py` (mock mode) and opened `http://127.0.0.1:8080/`.
2. Read `#recent-toggle`: before the click, `textContent` was `View All ▼`
   (`innerHTML` = `View All <span>▼</span>`).
3. Clicked `#recent-toggle`. `#more-recent` gained the `open` class, but the
   span's text became the literal string `&#x25B4; Hide`; `innerHTML` was
   `View All <span>&amp;#x25B4; Hide</span>` and the arrow disappeared.
4. Cause: `templates/index.html` assigns the label with
   `span.textContent = ... ? '&#x25B4; Hide' : 'View All &#x25BC;'`.
   `textContent` does not decode HTML entities, so the entity is stored as
   text.

### Changes

- `templates/index.html`: the toggle now writes the characters `▴ Hide` /
  `View All ▾` through `textContent` instead of `&#x25B4;` / `&#x25BC;`.
- `tests/e2e/test_ui_pipeline.py`: `_assert_recent_toggle_label()` clicks the
  toggle both ways and asserts the label contains the real arrow characters and
  no `&#`.

### Verification

- `pytest -q`: `83 passed, 1 deselected in 223.15s`.
- `pytest -m e2e`: `1 passed, 83 deselected in 21.60s`.
- Browser re-check after the fix: expanded label `▴ Hide`, collapsed label
  `View All ▾`, no literal entity text.

### Data changes

None.

## Post-audit Task 2 — Sidebar navigation (2026-10-29)

**Status:** complete.

### Baseline (recorded before changing)

In the running dashboard, all seven non-dashboard sidebar links had `href="#"`,
`class="nav-disabled"`, and `aria-disabled="true"`. Clicking "Content Studio"
left the URL at `/`, kept Dashboard active, and did not load a page. The inline
handler called `preventDefault()` for every sidebar link before checking
`aria-disabled`, so even a real `href` would not navigate.

### Changes

- `templates/_sidebar.html`: one shared sidebar partial. Each item is a real
  link (`/`, `/content-studio`, `/ideas`, `/content-pipeline`, `/assets`,
  `/projects`, `/analytics`, `/settings`). The server passes `active` and the
  partial adds `class="active"` plus `aria-current="page"` to the matching item.
- `templates/index.html`: includes the partial and the click handler that called
  `preventDefault()` was removed, so the browser navigates normally. The header
  Settings link now points at `/settings`.
- `templates/coming_soon.html`: shared layout for the six placeholder sections.
- `templates/settings.html`: real `/settings` page (placeholder body for now;
  Task 4 replaces it with provider management).
- `dashboard/app.py`: `/settings` plus the six Coming-soon routes, driven by
  `COMING_SOON_PAGES`.
- `static/style.css`: styles for the secondary pages.
- `tests/e2e/conftest.py`: the real-server fixture moved here so both e2e files
  share it (`base_url`, `data`, `log`, `artifacts`).
- `tests/e2e/test_ui_navigation.py`: clicks every sidebar link from the
  dashboard, asserts the URL, `<title>`, exactly one active item with
  `aria-current="page"`, that the sidebar contains no literal `&#` entity, and
  that no console error, page error, or `/api/` response ≥ 400 occurred.
  Screenshots: `tests/artifacts/e2e_nav_*.png`.

### Verification

- `pytest -q`: `83 passed, 2 deselected in 213.33s`.
- `pytest -m e2e`: `2 passed, 83 deselected in 28.54s` (pipeline + navigation).
- Browser screenshots confirmed the active highlight follows the page and the
  sidebar icons render as glyphs. The first navigation run exposed a second
  entity bug: the macro arguments were HTML entities and Jinja escaped them, so
  the sidebar showed `&#x25A4;` as text. The icons are now passed as literal
  characters and the e2e asserts no `&#` in the sidebar.

### Data changes

None.

## Post-audit Task 3 — Story-poll black thumbnail (2026-10-29)

**Status:** complete.

### Reproduction (recorded before fixing)

1. Opened the dashboard against the real `data/` root.
2. Item 15 (`Format sweep story-poll`, STORY_POLL, done) maps to
   `data/renders/item_15/frame_1.png` and `frame_2.png`. Both exist, are
   `1080x1920`, and have 754 distinct colours each, so the render itself is
   fine and the preview route returns them (`naturalWidth=1080`,
   `naturalHeight=1920` in the browser).
3. The card thumbnail is `.content-thumb img` with `height: 110px`,
   `width: 100%`, `object-fit: cover`. With a 526 px-wide card the image
   displays at 526x935 and the default `object-position: 50% 50%` crops the
   middle band (y≈412–522). That band of `frame_1.png` contains exactly one
   distinct colour — solid black — because the frame's text sits in the top
   third and the rest is empty background.
4. Therefore the thumbnail looked black even though the asset was healthy:
   **root cause is the thumbnail crop, not rendering, field mapping, or the
   preview route.** Evidence: `tests/artifacts/task3_before_thumb.png`.

### Changes

- `static/style.css`: `.content-thumb img` now sets
  `object-position: top center`, so tall story/reel frames crop from the top
  where the text is. This applies to every thumbnail and leaves the assets
  untouched.
- `tests/test_renderer.py`: `test_story_poll_frames_are_not_blank` asserts every
  STORY_POLL frame is `1080x1920`, has more than one distinct colour, and that
  the top band used by the thumbnail crop is not blank.
- `tests/e2e/test_ui_pipeline.py`: `_assert_story_thumbnail_shows_content`
  checks the published story card image is a loaded 1080x1920 asset with a
  top-anchored crop (`50% 0%`).

### Verification

- `pytest tests/test_renderer.py -q`: `12 passed`.
- `pytest -m e2e`: `2 passed, 84 deselected`.
- After the fix the card thumbnail shows "Frame 1 / 2" and the headline:
  `tests/artifacts/task3_after_thumb.png`.

### Data changes

None. No render or item file was regenerated, edited, or deleted, so no
`data/_backup_<timestamp>/` was required for this task.

