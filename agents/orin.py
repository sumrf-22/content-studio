from pathlib import Path
def run(item):
    out = Path(__file__).resolve().parent.parent / "data" / "published"
    out.mkdir(exist_ok=True)
    (out / f"item_{item['id']}.json").write_text(
        __import__("json").dumps(item, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return "Saved locally (publishing is intentionally disabled in v1)."
