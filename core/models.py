"""Canonical per-format copy schemas.

Vera produces copy and Kite renders it. Both sides import this module so the
field names cannot drift: every format has exactly one shape, and Vera validates
its output against it before returning.
"""

SUPPORTED_FORMATS = (
    "CAROUSEL",
    "SINGLE_IMAGE",
    "REEL",
    "INFOGRAPHIC",
    "TEXT_POST",
    "MEME",
    "STORY_POLL",
)


def _text(value):
    return "" if value is None else str(value).strip()


def _slide_dict(slide):
    if isinstance(slide, dict):
        return {
            "headline": _text(slide.get("headline")),
            "subheadline": _text(slide.get("subheadline") or slide.get("sub_headline")),
            "body": _text(slide.get("body")),
            "cta": _text(slide.get("cta")),
            "visual_direction": _text(
                slide.get("visual_direction") or slide.get("visual")
            ),
        }
    if isinstance(slide, str):
        lines = [line.strip() for line in slide.splitlines() if line.strip()]
        return {
            "headline": lines[0] if lines else "",
            "subheadline": "",
            "body": " ".join(lines[1:]),
            "cta": "",
            "visual_direction": "",
        }
    raise ValueError("carousel slides must be objects or strings")


def _scene_dict(scene):
    if isinstance(scene, dict):
        return {
            "visual_direction": _text(
                scene.get("visual_direction") or scene.get("visual")
            ),
            "on_screen_text": _text(scene.get("on_screen_text")),
            "duration": _text(scene.get("duration")),
        }
    if isinstance(scene, str):
        return {
            "visual_direction": _text(scene),
            "on_screen_text": "",
            "duration": "",
        }
    raise ValueError("reel scenes must be objects or strings")


def _string_list(value, name):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return [_text(item) for item in value if _text(item)]


def normalize_copy(data, fmt=None):
    """Return the canonical copy dict for a format or raise ValueError."""
    if not isinstance(data, dict):
        raise ValueError("copy must be an object")

    fmt = _text(fmt or data.get("format") or "CAROUSEL").upper()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"unsupported format {fmt!r}")

    canonical = {
        "format": fmt,
        "raw": data.get("raw", ""),
    }

    if fmt == "CAROUSEL":
        slides = data.get("slides")
        if not isinstance(slides, list):
            raise ValueError("carousel slides must be a list")
        canonical["slides"] = [_slide_dict(slide) for slide in slides]
        if not canonical["slides"]:
            raise ValueError("carousel needs at least one slide")
        canonical["caption"] = _text(data.get("caption"))
        canonical["hashtags"] = _text(data.get("hashtags"))

    elif fmt == "SINGLE_IMAGE":
        canonical.update({
            "headline": _text(data.get("headline")),
            "supporting_text": _text(data.get("supporting_text")),
            "visual_concept": _text(data.get("visual_concept")),
            "cta": _text(data.get("cta")),
            "caption": _text(data.get("caption")),
            "hashtags": _text(data.get("hashtags")),
        })

    elif fmt == "REEL":
        scenes = data.get("scenes")
        if not isinstance(scenes, list):
            raise ValueError("reel scenes must be a list")
        canonical.update({
            "hook": _text(data.get("hook")),
            "script": _text(data.get("script")),
            "scenes": [_scene_dict(scene) for scene in scenes],
            "visual_action_direction": _text(data.get("visual_action_direction")),
            "on_screen_text": _text(data.get("on_screen_text")),
            "cta": _text(data.get("cta")),
            "caption": _text(data.get("caption")),
            "hashtags": _text(data.get("hashtags")),
        })

    elif fmt == "INFOGRAPHIC":
        canonical.update({
            "title": _text(data.get("title") or data.get("headline")),
            "sections_data_points": _text(data.get("sections_data_points")),
            "visual_structure": _text(data.get("visual_structure")),
            "cta": _text(data.get("cta")),
            "caption": _text(data.get("caption")),
            "hashtags": _text(data.get("hashtags")),
        })

    elif fmt == "TEXT_POST":
        canonical.update({
            "post_text": _text(data.get("post_text")),
            "hook_opening": _text(data.get("hook_opening")),
            "cta": _text(data.get("cta")),
            "caption": _text(data.get("caption") or data.get("caption_text")),
            "hashtags": _text(data.get("hashtags")),
        })

    elif fmt == "MEME":
        canonical.update({
            "setup": _text(data.get("setup")),
            "punchline": _text(data.get("punchline")),
            "visual_concept": _text(data.get("visual_concept")),
            "caption": _text(data.get("caption") or data.get("caption_text")),
            "hashtags": _text(data.get("hashtags")),
        })

    elif fmt == "STORY_POLL":
        canonical.update({
            "frame_sequence": _string_list(data.get("frame_sequence"), "frames"),
            "text": _text(data.get("text")),
            "poll": _text(
                data.get("poll") or data.get("polls") or data.get("poll_question")
            ),
            "cta": _text(data.get("cta")),
            "caption": _text(data.get("caption")),
            "hashtags": _text(data.get("hashtags")),
        })

    return canonical


def fallback_copy(fmt, topic, error=None):
    """Return a valid canonical copy dict when parsing/validation fails."""
    fmt = _text(fmt).upper()
    if fmt not in SUPPORTED_FORMATS:
        fmt = "CAROUSEL"
    topic = _text(topic) or "Untitled"

    base = {
        "format": fmt,
        "raw": topic,
        "caption": "",
        "hashtags": "",
    }
    if error:
        base["validation_error"] = str(error)

    if fmt == "CAROUSEL":
        base["slides"] = [{
            "headline": topic,
            "subheadline": "",
            "body": "",
            "cta": "",
            "visual_direction": "",
        }]
    elif fmt == "SINGLE_IMAGE":
        base.update({"headline": topic, "supporting_text": "", "visual_concept": "",
                     "cta": ""})
    elif fmt == "REEL":
        base.update({"hook": "", "script": "", "scenes": [], "visual_action_direction": "",
                     "on_screen_text": "", "cta": ""})
    elif fmt == "INFOGRAPHIC":
        base.update({"title": topic, "sections_data_points": "", "visual_structure": "",
                     "cta": ""})
    elif fmt == "TEXT_POST":
        base.update({"post_text": topic, "hook_opening": "", "cta": ""})
    elif fmt == "MEME":
        base.update({"setup": topic, "punchline": "", "visual_concept": "", "cta": ""})
    elif fmt == "STORY_POLL":
        base.update({"frame_sequence": [topic], "text": "", "poll": "", "cta": ""})

    return base
