# Data store

Content Studio has no database server. The store is a single JSON document
(`data/state.json`) plus generated files on disk. `core/state.py` is the only
module that reads or writes the state document.

This is deliberate for a single-operator local tool (D-014). The invariants and
limits below are what a future SQLite/Postgres migration would have to preserve.

## Layout

```
data/
├── .gitkeep                     tracked; keeps the folder in a fresh clone
├── state.json                   pipeline state (gitignored)
├── renders/
│   └── item_<id>/
│       ├── slide_1.png ...      CAROUSEL
│       ├── single_image.png     SINGLE_IMAGE
│       ├── scene_1.png ...      REEL
│       ├── scene_1.txt ...      REEL shot notes
│       ├── infographic.png      INFOGRAPHIC
│       ├── meme.png             MEME
│       ├── text_post.txt        TEXT_POST
│       └── frame_1.png ...      STORY_POLL
├── published/
│   └── item_<id>.json           snapshot written at publish time
├── settings/
│   └── providers.json           encrypted BYOK provider list (gitignored)
└── _backup_<timestamp>/         operator backups (gitignored)
```

`data/state.json`, `data/renders/`, `data/published/`, `data/settings/`, and
`data/_backup_*/` are gitignored. A fresh clone has only `data/.gitkeep` and
starts with an empty pipeline, which is the intended behaviour (D-015).

The root is overridable with `CONTENT_STUDIO_DATA_DIR`. It is resolved once at
import time, so set it before starting the process (D-018).

## `state.json`

Top level:

```json
{
  "items": [],
  "activity": []
}
```

`load()` returns exactly this shape when the file is missing, empty, corrupt, or
structurally wrong. That keeps the app alive but silently discards a bad file
from the request's point of view; back up before maintenance (see below).

### Item

| Field | Type | Presence | Notes |
|---|---|---|---|
| `id` | integer | always | `max(existing) + 1`; never reused. |
| `topic` | string | always | Trimmed, ≤ 300 characters. |
| `stage` | string | always | `idea`, `idea_review`, `copy`, `design`, `publish`, `done`. |
| `status` | string | always | `pending_approval` or `published_local`. |
| `ideas` | array | always | `[]` until Atlas runs. |
| `copy` | object \| null | always | Canonical copy dict after `select_idea`. |
| `design` | object \| null | always | Kite result after `approve_copy`. |
| `format` | string \| null | always | One of `SUPPORTED_FORMATS` after selection. |
| `published` | boolean | always | `false` until publish succeeds. |
| `created_at` | string | always | ISO-8601 UTC timestamp. |
| `selected_idea` | string | after `select_idea` | Exact title chosen. |
| `publish` | object | after `publish` | `{mode, target, message}` from Orin. |

Items are inserted at the front, so `/api/state` returns newest-first.

### Idea

| Field | Type | Notes |
|---|---|---|
| `title` | string | Unique within the item (case-insensitive dedupe). |
| `problem` | string | Audience problem the idea addresses. |
| `angle` | string | One-line approach. |
| `format` | string | One of the seven formats. |
| `format_reason` | string | Why the format fits. |

Atlas keeps at most seven ideas, one per format in mock mode. `select_idea`
requires an exact title match.

### Copy

Every copy object has `format` and `raw`. Format-specific fields:

| Format | Fields |
|---|---|
| `CAROUSEL` | `slides[]` of `{headline, subheadline, body, cta, visual_direction}`, `caption`, `hashtags` |
| `SINGLE_IMAGE` | `headline`, `supporting_text`, `visual_concept`, `cta`, `caption`, `hashtags` |
| `REEL` | `hook`, `script`, `scenes[]` of `{visual_direction, on_screen_text, duration}`, `visual_action_direction`, `on_screen_text`, `cta`, `caption`, `hashtags` |
| `INFOGRAPHIC` | `title`, `sections_data_points`, `visual_structure`, `cta`, `caption`, `hashtags` |
| `TEXT_POST` | `post_text`, `hook_opening`, `cta`, `caption`, `hashtags` |
| `MEME` | `setup`, `punchline`, `visual_concept`, `caption`, `hashtags` |
| `STORY_POLL` | `frame_sequence[]` (strings), `text`, `poll`, `cta`, `caption`, `hashtags` |

`normalize_copy()` trims strings, accepts legacy aliases (`sub_headline`,
`visual`, `caption_text`, `polls`, `poll_question`, `headline` for infographic
title), and raises `ValueError` for a wrong shape. `fallback_copy()` produces a
valid object with `validation_error` when parsing fails.

### Design

| Format | Shape |
|---|---|
| `CAROUSEL` | `{provider: "local-pillow", count, slides: [{slide, file, url, visual_prompt}]}` |
| `SINGLE_IMAGE` | `{provider, count: 1, slides: [{slide: 1, file, url}]}` |
| `REEL` | `{provider, count, scenes: [{scene, file, scene_card, scene_meta, duration, url}]}` |
| `INFOGRAPHIC` | `{provider, count: 1, slides: [{slide: 1, file, url}]}` |
| `MEME` | `{provider, count: 1, slides: [{slide: 1, file, url}]}` |
| `TEXT_POST` | `{provider, count: 0, slides: [], text_file, text_preview}` |
| `STORY_POLL` | `{provider, count, frames: [{frame, file, url}]}` |

`file`, `scene_card`, `scene_meta`, and `text_file` are project-relative paths
such as `data/renders/item_9/slide_1.png`. `url` is `null` unless
`IMGBB_API_KEY` is set, in which case it is the imgbb URL.

### Publish metadata

```json
{"mode": "mock", "target": "local", "message": "Saved locally (mock publisher; no Instagram API call)."}
```

Only `mode=mock` is accepted. See `docs/INTEGRATIONS.md`.

### Activity

```json
{"time": "2026-10-29T10:04:00+00:00", "message": "Kite rendered 3 assets for item 16"}
```

Newest-first, capped at 100 entries in `add_activity()`. Entries are
append-only from the API's perspective; nothing prunes older ones beyond the cap.

### Published snapshot

`data/published/item_<id>.json` is the complete item object at publish time,
written after the item reaches `stage=done` / `status=published_local` and after
`publish` metadata is attached. It is a point-in-time copy, not a live view. A
later change to state does not rewrite it; there are no later changes because
`done` accepts no actions.

## Id allocation

`next_id()` uses `max(item.id) + 1`, not `len(items) + 1`. Deleting an item (done
by hand, since no API deletes) can therefore never make a new item reuse an
existing id. The trade-off is that ids are not contiguous.

## Writes and crash safety

`save()`:

1. Creates a `tempfile.mkstemp` file inside the data directory.
2. `json.dump(..., indent=2, ensure_ascii=False)`, flush, `fsync`.
3. `os.replace(temp, state.json)`, retrying on `PermissionError` 20 times at
   50 ms intervals (Windows readers can hold the destination open).
4. On any failure, unlinks the temp file and re-raises.

`_SAVE_LOCK` is a re-entrant lock. `action()` holds it for the whole
load → mutate → save cycle; `create_item()` holds it for its own cycle;
`save()` re-acquires it safely.

## Invariants

A valid store should satisfy:

- Item ids are unique and positive.
- `stage` is one of the six known values; `status` is one of the two emitted
  values.
- `format`, when set, is in `SUPPORTED_FORMATS`.
- `copy.format` equals `format` when both exist.
- Every design path resolves under `data/renders/item_<id>/` (or the configured
  equivalent).
- `published=true` implies `stage=done`, `status=published_local`, and a
  matching snapshot file.
- `activity` has at most 100 entries and every entry has `time` and `message`.
- Asset folders with no matching item are orphans, not references; the app
  never reads them unless a state entry points there.

## Backups and restore

Before any manual migration or cleanup:

```powershell
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item -Recurse data "data\_backup_$stamp"
```

Restore while the server is stopped:

1. Copy the backup's `state.json` back to `data/state.json`.
2. Copy any needed `renders/` and `published/` files back.
3. Start the server and check `/api/state` for the expected item count.

The repository has two historical backups:
`data/_backup_20261029_092442/` (Phase 0 baseline) and
`data/_backup_20261029_phase3/` (17 orphan render artifacts plus a
`MANIFEST.json`). Both are gitignored and untouched by the app.

## `settings/providers.json`

Managed by `core/settings.py`, not `core/state.py`. One file, whole-document
rewrite, same atomic-replace pattern as state.

```json
{
  "version": 1,
  "providers": [
    {
      "id": "9f2c1b7a4d10",
      "name": "OpenRouter",
      "base_url": "https://openrouter.ai/api/v1",
      "model": "openrouter/free",
      "enabled": true,
      "is_default": true,
      "api_key": "gAAAAAB... (Fernet token)",
      "api_key_last4": "ab12",
      "created_at": "2026-10-29T10:00:00+00:00",
      "updated_at": "2026-10-29T10:00:00+00:00"
    }
  ]
}
```

Invariants:

- `api_key` is always a Fernet token encrypted with
  `CONTENT_STUDIO_SECRET_KEY`; the raw key is never stored.
- `api_key_last4` is the only plaintext fragment and only feeds the mask.
- At most one provider has `is_default: true`. The first provider is promoted
  automatically; deleting the default promotes a replacement.
- The mode is live only when the default is `enabled` and has `api_key`;
  otherwise generation is mock.
- A missing/invalid secret key makes decryption fail loudly; the file is not
  rewritten on that path.

`data/settings/` is gitignored, so a clone does not inherit provider state. The
same "back up, don't delete" rule applies: copy the folder before editing it by
hand.

## Retention and cleanup

- There is no delete endpoint and no automatic pruning of items or renders.
- Activity is capped at 100 entries.
- Publishing does not copy renders; the snapshot only records their paths.
- Removing an item by hand leaves its render folder and publish snapshot behind.
  Treat those as orphans and move them to a backup folder rather than deleting
  them.

## Known data notes (2026-10-29)

- The real store holds items 1–16. Item 4 is intentionally parked at
  `stage=copy` from earlier manual testing; it is not a defect.
- Items 1 and 2 predate the canonical copy schema and carry legacy flat copy
  dicts. Normalization handles them; their stored copy is not rewritten.
- `data/published/` still contains `item_18.json` and `item_19.json` from
  pre-cleanup test items that no longer exist in state. They are harmless
  orphans, retained under the "back up, don't delete" rule.
- Render folders for old item ids may still exist after Phase 3 moved the
  orphaned ones out; only folders referenced by state are served.

## Schema evolution

There is no `schema_version` field. Code treats absent fields as defaults, so
adding an optional field is backward compatible:

1. Add the field with a default in `create_item()` or read it with `.get()`.
2. Do not rename existing fields without a migration; `copy` and `design` are
   consumed by both Vera/Kite and the dashboard.
3. For a breaking change, back up `data/`, write a one-off migration script, and
   record the decision in `docs/DECISIONS.md`.

If the pipeline grows beyond one process or needs concurrent writers, move to a
transactional store rather than adding another lock; the JSON design assumes one
writer and whole-document rewrites.
