import json

from core.state import DATA


def run(item):
    """Write the local publish package for ``item`` into ``<data>/published``."""
    out = DATA / "published"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"item_{item['id']}.json").write_text(
        json.dumps(item, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return "Saved locally (publishing is intentionally disabled in v1)."
