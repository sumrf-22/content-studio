"""Phase 2 regression tests: one canonical copy shape per format, and every
format renders its own assets into its own folder.

These tests run in mock mode (no OPENROUTER_API_KEY), so Vera's mock output is
exercised end to end: mock text -> parser -> canonical copy -> Kite renderer.
"""

from pathlib import Path

import pytest
from PIL import Image

from agents import kite, vera
from agents.atlas import run as atlas


FORMATS = [
    "CAROUSEL",
    "SINGLE_IMAGE",
    "REEL",
    "INFOGRAPHIC",
    "TEXT_POST",
    "MEME",
    "STORY_POLL",
]

EXPECTED_KEYS = {
    "CAROUSEL": {"format", "raw", "slides", "caption", "hashtags"},
    "SINGLE_IMAGE": {
        "format", "raw", "headline", "supporting_text", "visual_concept",
        "cta", "caption", "hashtags",
    },
    "REEL": {
        "format", "raw", "hook", "script", "scenes",
        "visual_action_direction", "on_screen_text", "cta", "caption",
        "hashtags",
    },
    "INFOGRAPHIC": {
        "format", "raw", "title", "sections_data_points",
        "visual_structure", "cta", "caption", "hashtags",
    },
    "TEXT_POST": {
        "format", "raw", "post_text", "hook_opening", "cta", "caption",
        "hashtags",
    },
    "MEME": {
        "format", "raw", "setup", "punchline", "visual_concept", "caption",
        "hashtags",
    },
    "STORY_POLL": {
        "format", "raw", "frame_sequence", "text", "poll", "cta", "caption",
        "hashtags",
    },
}


@pytest.fixture()
def render_dir(tmp_path, monkeypatch):
    """Redirect Kite output into a temporary folder for each test."""
    target = tmp_path / "renders"
    monkeypatch.setattr(kite, "RENDER_DIR", target)
    return target


def test_atlas_mock_offers_one_idea_per_format():
    ideas = atlas("a brand new topic nobody canned")
    assert [idea["format"] for idea in ideas] == FORMATS


@pytest.mark.parametrize("fmt", FORMATS)
def test_vera_returns_canonical_shape(fmt):
    copy = vera.run("kitchen storage habits", fmt)
    assert copy["format"] == fmt
    assert set(copy) == EXPECTED_KEYS[fmt]


@pytest.mark.parametrize("fmt", FORMATS)
def test_kite_renders_own_folder_and_preview_files(fmt, render_dir):
    copy = vera.run("kitchen storage habits", fmt)
    design = kite.run(9200, copy, fmt)

    item_dir = render_dir / "item_9200"
    assert item_dir.is_dir()

    stored = []
    for group in ("slides", "frames", "scenes"):
        stored += [entry["file"] for entry in design.get(group, []) or []]
    if design.get("text_file"):
        stored.append(design["text_file"])

    assert stored, f"{fmt} produced no asset paths"

    for relative in stored:
        path = Path(relative)
        candidate = path if path.is_absolute() else kite.BASE_DIR / path
        assert candidate.is_file(), f"{fmt} path missing: {relative}"

    if fmt == "STORY_POLL":
        for png in item_dir.glob("frame_*.png"):
            with Image.open(png) as image:
                assert image.size == (1080, 1920)
    elif fmt == "TEXT_POST":
        text = (item_dir / "text_post.txt").read_text(encoding="utf-8")
        assert "\\n" not in text, "literal backslash-n leaked into the text post"
        assert design["text_preview"]
    else:
        assert design["count"] >= 1
        assert list(item_dir.glob("*.png")), f"{fmt} created no PNG assets"


def test_kite_never_writes_placeholder_folders(render_dir):
    for index, fmt in enumerate(FORMATS):
        copy = vera.run("kitchen storage habits", fmt)
        kite.run(9300 + index, copy, fmt)

    names = {path.name for path in render_dir.iterdir()}
    assert "item_placeholder" not in names
    assert "item_pending" not in names


def test_kite_stores_project_relative_paths():
    inside = kite.BASE_DIR / "data" / "renders" / "item_1" / "slide_1.png"
    assert kite._rel(inside) == "data/renders/item_1/slide_1.png"


def test_carousel_parser_accepts_mixed_case_headers():
    raw = (
        "Slide 1\n"
        "Headline: Mixed case title\n"
        "Sub-headline: Works\n"
        "Body: Body line\n"
        "Visual direction: Nice visual\n"
        "\nCaption\nMixed caption\nHashtags\n#one #two"
    )
    copy = vera._parse_llm_output(raw, "CAROUSEL")
    assert copy["slides"][0]["headline"] == "Mixed case title"
    assert copy["slides"][0]["visual_direction"] == "Nice visual"
    assert copy["caption"] == "Mixed caption"
