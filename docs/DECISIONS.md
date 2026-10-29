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
