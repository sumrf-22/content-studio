# Decisions

Phase-scoped decisions made without blocking on the user. Newest last.

## D-001 — Git root is the inner project folder

**Decision:** Initialise git in `D:\content_studio\content_studio`, not the outer
`D:\content_studio` container.

**Why:** All source, tests, docs, data and the existing `.gitignore` live in the
inner folder. Initialising at the outer folder would add a pointless nesting level
and make `docs/SETUP.md` paths ambiguous.

**Consequence:** The repository is named `content_studio` and its root contains
`run.py`, `agents/`, `core/`, `dashboard/`, `tests/` and `docs/`.

## D-002 — Reuse the existing Python 3.14.6 venv

**Decision:** Reuse `.venv` after verifying `pip install -r requirements.txt`
succeeds, instead of deleting and recreating it.

**Why:** The venv is already pinned to the interpreter that runs the app, and
recreating it would only discard a working environment. `.venv/` is gitignored, so
a fresh clone still follows the documented `py -m venv .venv` path.

## D-003 — Pin the installed versions and pytest 9.2.0

**Decision:** Pin `flask==3.1.3`, `requests==2.34.2`, `Pillow==12.3.0` and add
`pytest==9.2.0`.

**Evidence:** `pip list --format=freeze` in the baseline venv showed those exact
versions. PyPI reported pytest 9.2.0 as the latest release on 2026-10-27 with
`requires_python >=3.10` (verified at `https://pypi.org/pypi/pytest/json`).

**Consequence:** Baseline behaviour does not change; installs are reproducible.

## D-004 — Local git identity

**Decision:** Set repository-local `user.name = "Content Studio Dev"` and
`user.email = "dev@localhost"`.

**Why:** No global git identity was configured, and commits are required per phase.
These values are local to this repository only.

## D-005 — Back up `data/` before the first fix

**Decision:** Copy all of `data/` to `data/_backup_20261029_092442/` and verify the
`state.json` hash before making changes.

**Why:** The ground rules forbid deleting user data without a backup. The copy
contains 49 files and the state hash matches.

## D-006 — Keep `data/` untracked for now

**Decision:** Leave the existing `.gitignore` rule (`data/`) in place for Phase 0.

**Why:** Phase 3 narrows the ignore list to generated renders only. Committing live
state or publish packages now would mix user data with source history before the
storage layout is settled.

## D-007 — JSON storage stays until Phase 3

**Decision:** Defer the repository-interface and storage decision to Phase 3 as
instructed.

**Why:** Phase 1 fixes are UI-critical and must not be bundled with a storage
refactor.

## D-008 — One stage-aware action vocabulary

**Decision:** Use exactly six action names in both the browser and the server:
`approve_idea`, `select_idea`, `approve_copy`, `approve_design`, `publish`, and
`reject`. `dashboard/app.py` holds `STAGE_ACTIONS`; an action is accepted only at
the listed stages.

**Why:** The UI previously generated `approve_<stage>`, producing names such as
`approve_idea_review` that the server rejected with 400. A single explicit map
removes the mismatch and returns a descriptive error for stale or invalid
actions.

**Consequence:** `approve_idea` is also allowed at `idea_review` when an item
has no ideas, so a previously stuck item can be regenerated. `select_idea`
requires `selected_idea` and moves the item from `idea_review` to `copy`.

## D-009 — Mock Atlas has a generic fallback

**Decision:** If a topic matches none of the canned mock branches, Atlas returns
three generic ideas (CAROUSEL, SINGLE_IMAGE, TEXT_POST) derived from the topic
line.

**Why:** During acceptance, item 4 ("Easy morning routines for energy") matched
no mock branch and returned zero ideas, leaving the UI at "No ideas generated"
with no way forward. The fallback keeps any fresh topic usable in mock mode.

**Consequence:** Mock ideas are generic for unmatched topics. Real LLM mode is
unaffected.

## D-010 — One canonical copy schema per format

**Decision:** `core/models.py` owns the only copy shape for each of the seven
formats. Vera validates and normalizes its parser output through
`normalize_copy()` and returns `fallback_copy()` when parsing fails. Kite calls
`normalize_copy()` again at its boundary.

**Why:** Vera and Kite had drifted apart (`visual_direction` vs. other names,
REEL scenes as strings vs. dicts), which crashed the renderer and produced empty
previews. A shared schema makes field drift a test failure instead of a runtime
error.

**Consequence:** Adding or renaming a field requires changing `core/models.py`
first. Unknown fields are dropped at the boundary, so the LLM cannot smuggle
arbitrary keys into `state.json`.

## D-011 — Mock Vera routes on the format name, not keywords

**Decision:** `core/llm.py` reads the selected format from the exact
`OUTPUT FORMAT - <FORMAT>` line in Vera's prompt and returns the matching mock
block.

**Why:** Keyword matching on "caption" made every format return carousel copy,
so the browser flow could not exercise the other six renderers.

**Consequence:** The mock depends on that prompt line staying stable. A change to
`_build_format_prompt()` must keep the line or update the mock parser.

## D-012 — Render assets are project-relative and served through `/api/asset`

**Decision:** Kite stores paths such as `data/renders/item_9/slide_1.png`
(forward slashes, relative to the project root). `/api/asset` serves only
`data/renders/` and `static/assets/` and rejects absolute, drive-letter, or
`..` paths. The UI also rewrites legacy absolute Windows paths before requesting
them.

**Why:** Absolute Windows paths never resolved in the browser, so every preview
404'd, and a static-folder-only allowlist could not reach generated renders.

**Consequence:** Moving render output out of `data/renders/` requires updating
the allowlist. Old state entries with absolute paths keep working through the
UI rewrite.

## D-013 — `core/state.py` retries the atomic replace on Windows

**Decision:** Serialize `save()` with a process lock and retry `os.replace` up to
20 times (50 ms apart) when Windows reports `PermissionError`.

**Why:** `POST /api/idea` returned 500 with
`PermissionError: [WinError 5]` while another request was reading `state.json`.
Windows denies the replace while the destination has an open handle.

**Consequence:** Writes can take up to one extra second under contention but no
longer fail. Multi-process deployments still need a single writer; that belongs
to the storage phase.

## D-014 — Phase 3 covers data integrity, not a database migration

**Decision:** Keep `state.json` as the store for now and treat Phase 3 as data
integrity plus cleanup: serialized mutations, collision-free ids, validated
request bodies, and the leftover audit items. A repository interface or a real
database moves to a later phase, after the API surface is frozen.

**Why:** The pipeline is single-user and local. Concurrency and validation were
producing real 500s and wrong-format renders; a storage rewrite would add risk
without fixing a demonstrated failure.

**Consequence:** `core/state.py` stays the only module that reads or writes
`data/state.json`. Adding a database means reimplementing `load`, `save`,
`create_item`, `next_id`, and `locked`, plus the tests that patch those globals.

## D-015 — Ignore generated data, keep `data/` present

**Decision:** `.gitignore` ignores `data/state.json`, `data/.state-*.tmp`,
`data/renders/`, `data/published/`, `data/_backup_*/`, and `tests/artifacts/`
instead of the whole `data/` folder. `data/.gitkeep` is tracked.

**Why:** A blanket `data/` rule also hid the folder from a fresh clone, and live
pipeline state is operator data that should not enter source history.

**Consequence:** A fresh clone starts with an empty pipeline; `core/state.py`
recreates the folder on first run. Anyone who wants seed content must copy a
state file in explicitly.

## D-016 — Localhost by default, one shared token for anything else

**Decision:** Default bind is `127.0.0.1`, debug is off, and any non-loopback
bind requires `CONTENT_STUDIO_TOKEN`. Authentication is a single shared secret
presented as a header, a cookie, or a one-time `?token=` URL.

**Why:** The app runs an LLM pipeline that writes files and, in debug mode,
exposes an interactive console. A single-operator tool does not need accounts,
but it does need a hard stop before a network bind and a way to authorize remote
access.

**Consequence:** There is no user model and no per-item authorization. Rotating
the token and restarting revokes all clients. A multi-user deployment needs a
real auth layer and a WSGI server, both explicitly out of scope.

## D-017 — CSRF is blocked by requiring same-origin JSON

**Decision:** Mutating requests must send `application/json`, and `Origin` /
`Sec-Fetch-Site` must match the app when present. No CSRF token is issued.

**Why:** The frontend already sends JSON, so the rule costs nothing. A cross-site
HTML form cannot set that content type, and browsers mark cross-site `fetch`
calls with `Origin` and `Sec-Fetch-Site`, so both classic CSRF and scripted
cross-site posts are rejected at the guard.

**Consequence:** Any future form-based UI or non-browser client must send JSON and
an honest `Origin`. API tests that post form data will get `415` by design.
