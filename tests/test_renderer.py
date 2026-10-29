"""Phase 5 renderer tests.

These assert the contract Kite makes to the API and the browser: a known
canvas size per format, PNG output, assets inside the item folder, and a
non-crashing failure shape for invalid copy.
"""

import pytest
from PIL import Image

from agents import kite, vera

FORMATS = [
    "CAROUSEL",
    "SINGLE_IMAGE",
    "REEL",
    "INFOGRAPHIC",
    "TEXT_POST",
    "MEME",
    "STORY_POLL",
]

# format -> (glob, width, height)
CANVAS = {
    "CAROUSEL": ("slide_*.png", 1080, 1350),
    "SINGLE_IMAGE": ("single_image.png", 1080, 1350),
    "REEL": ("scene_*.png", 1080, 1920),
    "INFOGRAPHIC": ("infographic.png", 1080, 1350),
    "MEME": ("meme.png", 1080, 1350),
    "STORY_POLL": ("frame_*.png", 1080, 1920),
}

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture()
def render_dir(isolated_data):
    return isolated_data / "renders"


def _asset_paths(design):
    paths = []
    for group in ("slides", "frames", "scenes"):
        paths += [entry["file"] for entry in design.get(group, []) or []]
    if design.get("text_file"):
        paths.append(design["text_file"])
    return paths


@pytest.mark.parametrize("fmt", [f for f in FORMATS if f in CANVAS])
def test_each_image_format_uses_its_own_canvas(fmt, render_dir):
    copy = vera.run("kitchen storage habits", fmt)
    design = kite.run(700, copy, fmt)

    pattern, width, height = CANVAS[fmt]
    images = sorted((render_dir / "item_700").glob(pattern))

    assert images, f"{fmt} rendered no {pattern} files"
    for image_path in images:
        with Image.open(image_path) as image:
            assert image.format == "PNG"
            assert image.size == (width, height), f"{fmt}: {image.size}"
            assert image.mode in {"RGB", "RGBA"}

    assert design["count"] >= 1
    for relative in _asset_paths(design):
        assert (kite.DATA_ROOT.parent / relative).is_file(), relative


def test_carousel_renders_one_slide_per_copy_slide(render_dir):
    copy = vera.run("kitchen storage habits", "CAROUSEL")
    design = kite.run(701, copy, "CAROUSEL")

    assert design["count"] == len(copy["slides"])
    assert [entry["slide"] for entry in design["slides"]] == list(
        range(1, len(copy["slides"]) + 1)
    )
    assert sorted(p.name for p in (render_dir / "item_701").glob("*.png")) == [
        f"slide_{index}.png" for index in range(1, len(copy["slides"]) + 1)
    ]


def test_reel_writes_one_card_and_one_script_per_scene(render_dir):
    copy = vera.run("kitchen storage habits", "REEL")
    design = kite.run(702, copy, "REEL")

    assert design["count"] == len(copy["scenes"])
    assert len(list((render_dir / "item_702").glob("scene_*.png"))) == len(copy["scenes"])
    assert len(list((render_dir / "item_702").glob("scene_*.txt"))) == len(copy["scenes"])

    for entry in design["scenes"]:
        assert entry["file"].endswith(f"scene_{entry['scene']}.png")
        script = (render_dir / "item_702" / f"scene_{entry['scene']}.txt").read_text(
            encoding="utf-8"
        )
        assert script.strip()


def test_text_post_writes_real_newlines(render_dir):
    copy = vera.run("kitchen storage habits", "TEXT_POST")
    design = kite.run(703, copy, "TEXT_POST")

    assert design["count"] == 0
    text_path = render_dir / "item_703" / "text_post.txt"
    text = text_path.read_text(encoding="utf-8")

    assert "\\n" not in text
    assert "\n" in text
    assert copy["post_text"].splitlines()[0][:20] in text
    assert design["text_preview"]


def test_invalid_copy_returns_a_note_instead_of_raising(render_dir):
    design = kite.run(704, {"format": "CAROUSEL"}, "CAROUSEL")

    assert design["count"] == 0
    assert design["note"]
    assert not (render_dir / "item_704").exists() or not list(
        (render_dir / "item_704").glob("*.png")
    )


def test_rendering_creates_the_item_folder_under_the_data_root(render_dir):
    copy = vera.run("kitchen storage habits", "MEME")
    kite.run(705, copy, "MEME")

    item_dir = render_dir / "item_705"
    assert item_dir.is_dir()
    assert sorted(p.name for p in item_dir.iterdir()) == ["meme.png"]
