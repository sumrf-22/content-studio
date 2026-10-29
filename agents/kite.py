import os
import re
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from config import IMGBB_API_KEY
from core import models


BASE_DIR = Path(__file__).resolve().parent.parent
RENDER_DIR = BASE_DIR / "data" / "renders"

WIDTH = 1080
HEIGHT = 1350
HEIGHT_VERTICAL = 1920


def _rel(path):
    """Store asset paths relative to the project root, using forward slashes."""
    try:
        return Path(path).resolve().relative_to(BASE_DIR).as_posix()
    except ValueError:
        return str(path)


def _font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
    ]

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def _wrap(text, font, max_width):
    words = text.split()
    lines = []
    current = ""

    dummy = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    for word in words:
        test = f"{current} {word}".strip()

        if dummy.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def _extract_slides(copy_text):
    slides = []

    blocks = re.split(r"(?=SLIDE\s+\d+)", copy_text, flags=re.I)

    for block in blocks:
        if not re.search(r"SLIDE\s+\d+", block, re.I):
            continue

        headline = re.search(
            r"Headline:\s*(.+)",
            block,
            re.I
        )

        subheadline = re.search(
            r"Sub-headline:\s*(.+)",
            block,
            re.I
        )

        body = re.search(
            r"Body:\s*(.+)",
            block,
            re.I
        )

        cta = re.search(
            r"CTA:\s*(.+)",
            block,
            re.I
        )

        visual = re.search(
            r"Visual direction:\s*(.+)",
            block,
            re.I
        )

        slides.append({
            "headline": headline.group(1).strip() if headline else "",
            "subheadline": subheadline.group(1).strip() if subheadline else "",
            "body": body.group(1).strip() if body else "",
            "cta": cta.group(1).strip() if cta else "",
            "visual": visual.group(1).strip() if visual else "",
        })

    return slides[:5]


def _create_visual_background(slide, index):
    """
    Temporary local visual layer.

    We keep this local and deterministic so Kite works even before
    an external AI-image provider is connected.
    """

    img = Image.new("RGB", (WIDTH, HEIGHT))
    pixels = img.load()

    base = [
        (24, 30, 45),
        (30, 42, 55),
        (38, 35, 55),
        (32, 48, 43),
        (45, 38, 30),
    ][index % 5]

    for y in range(HEIGHT):
        factor = y / HEIGHT

        for x in range(WIDTH):
            glow = int(
                25
                * (1 - abs((x / WIDTH) - 0.5) * 2)
                * (1 - factor * 0.5)
            )

            pixels[x, y] = tuple(
                min(255, value + glow)
                for value in base
            )

    return img


def _create_vertical_scene_scene_card(scene_num, visual_direction, on_screen_text):
    """
    Create a scene-card asset for REEL format.
    1080x1350 is the fallback; the scene card is a standalone visual.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)

    # Dark background
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=(15, 20, 30))

    # Scene number badge
    font_num = _font(64, bold=True)
    text = f"SCENE {scene_num}"
    bbox = draw.textbbox((0, 0), text, font=font_num)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.rectangle(
        [(WIDTH // 2 - tw // 2 - 40, HEIGHT // 2 - th // 2 - 25),
         (WIDTH // 2 + tw // 2 + 40, HEIGHT // 2 + th // 2 + 15)],
        fill=(60, 140, 220), outline=(255, 255, 255), width=4
    )
    draw.text((WIDTH // 2, HEIGHT // 2 - th // 2), text, font=font_num, fill="white")

    # Visual direction
    font_dir = _font(44)
    lines_dir = _wrap(visual_direction, font_dir, 900)
    y_dir = HEIGHT // 2 + 60
    for line in lines_dir:
        draw.text((WIDTH // 2, y_dir), line, font=font_dir, fill=(220, 225, 230))
        y_dir += 60

    # On-screen text
    font_ost = _font(40)
    lines_ost = _wrap(on_screen_text, font_ost, 900)
    y_ost = HEIGHT // 2 + 200
    for line in lines_ost:
        draw.text((WIDTH // 2, y_ost), line, font=font_ost, fill=(255, 215, 0))
        y_ost += 55

    return img


def _render_slide(slide, index, output_path):
    img = _create_visual_background(slide, index)

    draw = ImageDraw.Draw(img)

    # Dark readability panel
    panel = (55, 70, 1025, 1110)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    od.rounded_rectangle(
        panel,
        radius=35,
        fill=(0, 0, 0, 150)
    )

    img = Image.alpha_composite(
        img.convert("RGBA"),
        overlay
    )

    draw = ImageDraw.Draw(img)

    title_font = _font(68, bold=True)
    subtitle_font = _font(38)
    body_font = _font(42)
    cta_font = _font(38, bold=True)
    small_font = _font(25)

    x = 95
    y = 120
    max_width = 890

    # Slide number
    draw.text(
        (x, 55),
        f"{index + 1:02d} / 05",
        font=small_font,
        fill="white"
    )

    # Headline
    headline = slide["headline"]

    for line in _wrap(headline, title_font, max_width):
        draw.text(
            (x, y),
            line,
            font=title_font,
            fill="white"
        )
        y += 82

    y += 25

    # Subheadline
    if slide["subheadline"]:
        for line in _wrap(slide["subheadline"], subtitle_font, max_width):
            draw.text(
                (x, y),
                line,
                font=subtitle_font,
                fill=(220, 225, 230)
            )
            y += 52

        y += 35

    # Body
    if slide["body"]:
        for line in _wrap(slide["body"], body_font, max_width):
            draw.text(
                (x, y),
                line,
                font=body_font,
                fill="white"
            )
            y += 58

        y += 35

    # CTA
    if slide["cta"]:
        for line in _wrap(slide["cta"], cta_font, max_width):
            draw.text(
                (x, y),
                line,
                font=cta_font,
                fill="white"
            )
            y += 52

    img.convert("RGB").save(
        output_path,
        "PNG",
        optimize=True
    )


def _render_single_image(copy_data, output_path):
    """
    Single-image format: exactly one 1080x1350 asset.
    """
    img = _create_visual_background({}, 0)
    draw = ImageDraw.Draw(img)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        (55, 70, 1025, 1110),
        radius=35,
        fill=(0, 0, 0, 150)
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(img)

    title_font = _font(76, bold=True)
    subtitle_font = _font(44)
    cta_font = _font(40, bold=True)
    max_width = 890

    headline = copy_data.get("headline", "")
    supporting = copy_data.get("supporting_text", "")
    cta = copy_data.get("cta", "")

    y = 120
    for line in _wrap(headline, title_font, max_width):
        draw.text((95, y), line, font=title_font, fill="white")
        y += 90
    y += 40

    if supporting:
        for line in _wrap(supporting, subtitle_font, max_width):
            draw.text((95, y), line, font=subtitle_font, fill=(220, 225, 230))
            y += 58
        y += 40

    if cta:
        for line in _wrap(cta, cta_font, max_width):
            draw.text((95, y), line, font=cta_font, fill="white")
            y += 60

    img.convert("RGB").save(output_path, "PNG", optimize=True)


def _render_infographic(copy_data, output_path):
    """
    Infographic format: exactly one 1080x1350 structured visual.
    """
    img = _create_visual_background({}, 0)
    draw = ImageDraw.Draw(img)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        (55, 70, 1025, 1110),
        radius=35,
        fill=(0, 0, 0, 150)
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(img)

    title_font = _font(72, bold=True)
    body_font = _font(42)
    small_font = _font(28)
    cta_font = _font(38, bold=True)
    max_width = 890

    title = copy_data.get("title", "")
    sections = copy_data.get("sections_data_points", "")
    structure = copy_data.get("visual_structure", "")
    cta = copy_data.get("cta", "")
    caption = copy_data.get("caption", "")

    y = 120
    for line in _wrap(title, title_font, max_width):
        draw.text((95, y), line, font=title_font, fill="white")
        y += 85
    y += 35

    # Draw section blocks
    if sections:
        font_section = _font(46)
        for section in sections.splitlines():
            if section.strip():
                for line in _wrap(section.strip(), font_section, max_width):
                    draw.text((95, y), line, font=font_section, fill=(255, 215, 0))
                    y += 58
            y += 20

    y += 30

    # Visual structure description
    if structure:
        for line in _wrap(structure, small_font, max_width):
            draw.text((95, y), line, font=small_font, fill=(220, 225, 230))
            y += 38
        y += 30

    if cta:
        for line in _wrap(cta, cta_font, max_width):
            draw.text((95, y), line, font=cta_font, fill="white")
            y += 55

    if caption:
        for line in _wrap(caption, small_font, max_width):
            draw.text((95, y), line, font=small_font, fill=(220, 225, 230))
            y += 35

    img.convert("RGB").save(output_path, "PNG", optimize=True)


def _render_text_post(copy_data, output_path):
    """
    Text-post format: text-first design package.

    No image asset; writes the post content as text inside the item's own
    render folder so every format has its own output directory.
    """
    hook = copy_data.get("hook_opening", "")
    text = copy_data.get("post_text", "")
    cta = copy_data.get("cta", "")
    caption = copy_data.get("caption", "")
    hashtags = copy_data.get("hashtags", "")

    text_path = Path(output_path)
    text_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    if hook:
        lines.append(f"HOOK: {hook}")
    if text:
        lines.append(f"POST_TEXT:\n{text}")
    if cta:
        lines.append(f"CTA: {cta}")
    if caption:
        lines.append(f"CAPTION: {caption}")
    if hashtags:
        lines.append(f"HASHTAGS: {hashtags}")

    body = "\n\n".join(lines)
    text_path.write_text(body, encoding="utf-8")

    return {
        "provider": "local-pillow",
        "text_file": _rel(text_path),
        "text_preview": body[:400],
        "slides": [],
        "count": 0,
    }


def _render_meme(copy_data, output_path):
    """
    Meme format: one 1080x1350 meme-style visual.
    Setup and punchline are rendered as text overlays.
    """
    img = _create_visual_background({}, 0)
    draw = ImageDraw.Draw(img)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        (55, 70, 1025, 1110),
        radius=35,
        fill=(0, 0, 0, 150)
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(img)

    title_font = _font(72, bold=True)
    small_font = _font(34)
    max_width = 890

    setup = copy_data.get("setup", "")
    punchline = copy_data.get("punchline", "")
    concept = copy_data.get("visual_concept", "")
    caption = copy_data.get("caption", "")

    y = 120
    for line in _wrap(concept, title_font, max_width):
        draw.text((95, y), line, font=title_font, fill="white")
        y += 85
    y += 30

    if setup:
        for line in _wrap(setup, small_font, max_width):
            draw.text((95, y), line, font=small_font, fill=(220, 225, 230))
            y += 44
        y += 25

    if punchline:
        for line in _wrap(punchline, small_font, max_width):
            draw.text((95, y), line, font=small_font, fill=(255, 215, 0))
            y += 44
        y += 25

    if caption:
        for line in _wrap(caption, small_font, max_width):
            draw.text((95, y), line, font=small_font, fill=(220, 225, 230))
            y += 35

    img.convert("RGB").save(output_path, "PNG", optimize=True)


def _render_story_poll(copy_data, output_dir):
    """
    Story-poll format: multiple 1080x1920 vertical frame assets.

    Frames are written into the item's own render folder.
    """
    frames = copy_data.get("frame_sequence", [])
    text = copy_data.get("text", "")
    poll = copy_data.get("poll", "")
    cta = copy_data.get("cta", "")
    caption = copy_data.get("caption", "")

    item_dir = Path(output_dir)
    item_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, frame in enumerate(frames, 1):
        frame_path = item_dir / f"frame_{i}.png"

        # Vertical canvas 1080x1920
        img = Image.new("RGB", (WIDTH, HEIGHT_VERTICAL))
        draw = ImageDraw.Draw(img)
        overlay = Image.new("RGBA", (WIDTH, HEIGHT_VERTICAL), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle(
            (55, 70, 1025, 1710),
            radius=35,
            fill=(0, 0, 0, 150)
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay)
        draw = ImageDraw.Draw(img)

        font_title = _font(64, bold=True)
        font_text = _font(40)
        font_small = _font(28)
        max_width = 890

        y = 120
        # Frame number
        draw.text(
            (95, 55),
            f"Frame {i} / {len(frames)}",
            font=_font(30),
            fill=(255, 215, 0)
        )

        # Frame text
        for line in _wrap(frame, font_title, max_width):
            draw.text((95, y), line, font=font_title, fill="white")
            y += 70
        y += 30

        # Additional text
        if text:
            for line in _wrap(text, font_text, max_width):
                draw.text((95, y), line, font=font_text, fill=(220, 225, 230))
                y += 52
            y += 30

        if poll:
            for line in _wrap(poll, font_text, max_width):
                draw.text((95, y), line, font=font_text, fill=(255, 215, 0))
                y += 52

        if cta:
            for line in _wrap(cta, font_title, max_width):
                draw.text((95, y), line, font=font_title, fill="white")
                y += 55
            y += 20

        if caption:
            for line in _wrap(caption, font_small, max_width):
                draw.text((95, y), line, font=font_small, fill=(220, 225, 230))
                y += 32

        img.convert("RGB").save(frame_path, "PNG", optimize=True)

        results.append({
            "frame": i,
            "file": _rel(frame_path),
            "url": None,
        })

    return {
        "provider": "local-pillow",
        "frames": results,
        "count": len(results),
    }


def _upload_imgbb(path):
    if not IMGBB_API_KEY:
        return None

    with open(path, "rb") as image_file:
        response = requests.post(
            "https://api.imgbb.com/1/upload",
            params={"key": IMGBB_API_KEY},
            files={"image": image_file},
            timeout=120,
        )

    response.raise_for_status()

    data = response.json()

    return data.get("data", {}).get("url")


def run(item_id, copy_data, format=None):
    """
    Kite: format-aware design renderer.

    Args:
        item_id: Item identifier for directory naming.
        copy_data: Structured copy dict from Vera (legacy plain text is still
            accepted for carousel copy).
        format: Optional format override. If None, detected from copy_data.

    Returns:
        Dict with provider, rendered assets, and count.
    """
    if format is None:
        if isinstance(copy_data, dict):
            format = copy_data.get("format", "CAROUSEL")
        else:
            format = "CAROUSEL"

    fmt = str(format).upper().strip()

    # Backward compatible: a string is treated as plain carousel copy.
    if isinstance(copy_data, str):
        slides = _extract_slides(copy_data)
        if not slides:
            raise ValueError("Kite could not find carousel slides in Vera's output.")

        item_dir = RENDER_DIR / f"item_{item_id}"
        item_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for index, slide in enumerate(slides):
            path = item_dir / f"slide_{index + 1}.png"
            _render_slide(slide, index, path)
            results.append({
                "slide": index + 1,
                "file": _rel(path),
                "url": _upload_imgbb(path),
                "visual_prompt": slide.get("visual", ""),
            })

        return {
            "provider": "local-pillow",
            "slides": results,
            "count": len(results),
        }

    # Validate at the renderer boundary so no branch below can read a field
    # name Vera did not produce.
    try:
        copy_data = models.normalize_copy(copy_data, fmt)
    except (ValueError, TypeError) as exc:
        return {
            "provider": "local-pillow",
            "slides": [],
            "count": 0,
            "note": f"invalid {fmt} copy: {exc}",
        }

    item_dir = RENDER_DIR / f"item_{item_id}"
    item_dir.mkdir(parents=True, exist_ok=True)

    if fmt == "CAROUSEL":
        results = []
        for index, slide in enumerate(copy_data["slides"]):
            path = item_dir / f"slide_{index + 1}.png"
            _render_slide(slide, index, path)
            results.append({
                "slide": index + 1,
                "file": _rel(path),
                "url": _upload_imgbb(path),
                "visual_prompt": slide.get("visual_direction", ""),
            })
        return {
            "provider": "local-pillow",
            "slides": results,
            "count": len(results),
        }

    if fmt == "SINGLE_IMAGE":
        path = item_dir / "single_image.png"
        _render_single_image(copy_data, path)
        return {
            "provider": "local-pillow",
            "slides": [{
                "slide": 1,
                "file": _rel(path),
                "url": _upload_imgbb(path),
            }],
            "count": 1,
        }

    if fmt == "INFOGRAPHIC":
        path = item_dir / "infographic.png"
        _render_infographic(copy_data, path)
        return {
            "provider": "local-pillow",
            "slides": [{
                "slide": 1,
                "file": _rel(path),
                "url": _upload_imgbb(path),
            }],
            "count": 1,
        }

    if fmt == "MEME":
        path = item_dir / "meme.png"
        _render_meme(copy_data, path)
        return {
            "provider": "local-pillow",
            "slides": [{
                "slide": 1,
                "file": _rel(path),
                "url": _upload_imgbb(path),
            }],
            "count": 1,
        }

    if fmt == "REEL":
        results = []
        for i, scene in enumerate(copy_data["scenes"], 1):
            card_path = item_dir / f"scene_{i}.png"
            _create_vertical_scene_scene_card(
                scene_num=i,
                visual_direction=scene.get("visual_direction", "Scene visual"),
                on_screen_text=scene.get("on_screen_text", ""),
            ).save(card_path, "PNG", optimize=True)

            scene_meta = item_dir / f"scene_{i}.txt"
            scene_meta.write_text(
                "\n".join([
                    f"Scene {i}: {scene.get('visual_direction', '')}",
                    f"On-screen text: {scene.get('on_screen_text', '')}",
                    f"Duration: {scene.get('duration', '')}",
                ]) + "\n",
                encoding="utf-8",
            )

            results.append({
                "scene": i,
                "file": _rel(card_path),
                "scene_card": _rel(card_path),
                "scene_meta": _rel(scene_meta),
                "duration": scene.get("duration", ""),
                "url": None,
            })

        return {
            "provider": "local-pillow",
            "scenes": results,
            "count": len(results),
        }

    if fmt == "TEXT_POST":
        return _render_text_post(copy_data, item_dir / "text_post.txt")

    if fmt == "STORY_POLL":
        return _render_story_poll(copy_data, item_dir)

    return {
        "provider": "local-pillow",
        "slides": [],
        "count": 0,
        "note": f"Unknown format '{fmt}'; no assets created",
    }
