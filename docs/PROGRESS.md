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
