

import re

from core import models
from core.llm import generate


SUPPORTED_FORMATS = list(models.SUPPORTED_FORMATS)


def _build_format_prompt(fmt, topic):
    """Return a format-specific prompt for Vera."""
    fmt_lower = fmt.lower().replace("_", " ").strip()
    topic_lower = topic.lower()

    if fmt == "CAROUSEL":
        structure = """SLIDE 1
Headline:
Sub-headline:
Visual direction:

SLIDE 2
Headline:
Body:
Visual direction:

SLIDE 3
Headline:
Body:
Visual direction:

SLIDE 4
Headline:
Body:
Visual direction:

SLIDE 5
Headline:
Body:
CTA:
Visual direction:

CAPTION
Write a concise Instagram caption related to the carousel.

HASHTAGS
Provide 5-10 relevant hashtags."""
        count_guidance = "Generate 3 to 6 slides based on the topic. Do NOT blindly force exactly 5 if the topic needs fewer or more."

    elif fmt == "REEL":
        structure = """HOOK
Write a short, attention-grabbing opening (1-2 sentences).

SCRIPT
Write a short video script (4-6 lines).

SCENES
List the scenes in order (Scene 1, Scene 2, etc.).

VISUAL_ACTION_DIRECTION
Describe what happens visually in each scene.

ON_SCREEN_TEXT
List what text should appear on screen.

CTA
Write a clear call-to-action.

CAPTION
Write a concise Instagram caption.

HASHTAGS
Provide 5-10 relevant hashtags."""
        count_guidance = "Generate a video storyboard with 3 to 30 scenes."

    elif fmt == "SINGLE_IMAGE":
        structure = """HEADLINE
Write a strong headline (one line).

SUPPORTING_TEXT
Write supporting text (2-4 lines).

VISUAL_CONCEPT
Describe the visual concept for the image.

CTA
Write a clear call-to-action.

CAPTION
Write a concise Instagram caption.

HASHTAGS
Provide 5-10 relevant hashtags."""
        count_guidance = "Generate 1 image/post slide."

    elif fmt == "INFOGRAPHIC":
        structure = """TITLE
Write the infographic title.

SECTIONS_DATA_POINTS
List the data points or sections with titles and values.

VISUAL_STRUCTURE
Describe the layout/structure of the infographic.

CTA
Write a call-to-action.

CAPTION
Write a concise Instagram caption.

HASHTAGS
Provide 5-10 relevant hashtags."""
        count_guidance = "Generate 1 image/post slide."

    elif fmt == "TEXT_POST":
        structure = """POST_TEXT
Write the full post text (10-15 lines).

HOOK_OPENING
Write a hook/opening line.

CTA
Write a call-to-action.

CAPTION
Write a concise Instagram caption.

HASHTAGS
Provide 5-10 relevant hashtags."""
        count_guidance = "Generate 1 image/post slide."

    elif fmt == "MEME":
        structure = """SETUP
Write the setup/punchline-1.

PUNNACLE
Write the punchline.

VISUAL_CONCEPT
Describe the visual concept.

CAPTION
Write a short caption.

HASHTAGS
Provide 3-5 relevant hashtags."""
        count_guidance = "Generate 1 image/post slide."

    elif fmt == "STORY_POLL":
        structure = """FRAME_SEQUENCE
List the frames in order (Frame 1, Frame 2, etc.).

TEXT
Write the on-screen text for each frame.

POLL_QUESTION
Write the poll/question to be asked.

CTA
Write a call-to-action.

CAPTION
Write a concise Instagram caption.

HASHTAGS
Provide 3-5 relevant hashtags."""
        count_guidance = "Generate 3 to 6 frames for the story/reel."

    else:
        structure = "CAPTION\nWrite a concise Instagram caption.\nHASHTAGS\nProvide 5-10 relevant hashtags."
        count_guidance = "Generate 3 to 5 slides."
        fmt_lower = "carousel"

    prompt = f"""
You are Vera, the social-media copywriting agent inside a human-approved Content Studio.

TOPIC:
{topic}

SELECTED FORMAT:
{fmt_lower}

OUTPUT FORMAT - {fmt.upper()}:
{structure}

CONTENT RULES:
- Do NOT return \"User Safety: safe\".
- Do NOT return analysis, explanations, or markdown code fences.
- Return ONLY the finished {fmt_lower} content.
- Follow the output format exactly.
- {count_guidance}
- Use plain text.
- Keep each section concise.

SELECTED TOPIC:
{topic}
"""
    return prompt


# Recognized field headers. Keys are normalized to upper case with runs of
# spaces/hyphens collapsed, then mapped through _ALIASES.
_ALIASES = {
    "SUB HEADLINE": "SUB_HEADLINE",
    "SUBHEADLINE": "SUB_HEADLINE",
    "VISUAL": "VISUAL_DIRECTION",
    "VISUAL DIRECTION": "VISUAL_DIRECTION",
    "PUNCHLINE": "PUNNACLE",
    "POLL QUESTION": "POLL_QUESTION",
    "SECTIONS DATA POINTS": "SECTIONS_DATA_POINTS",
    "VISUAL STRUCTURE": "VISUAL_STRUCTURE",
    "POST TEXT": "POST_TEXT",
    "HOOK OPENING": "HOOK_OPENING",
    "VISUAL CONCEPT": "VISUAL_CONCEPT",
    "FRAME SEQUENCE": "FRAME_SEQUENCE",
    "ON SCREEN TEXT": "ON_SCREEN_TEXT",
    "VISUAL ACTION DIRECTION": "VISUAL_ACTION_DIRECTION",
}

_KEYS = {
    "HEADLINE",
    "SUB_HEADLINE",
    "BODY",
    "VISUAL_DIRECTION",
    "CTA",
    "CAPTION",
    "HASHTAGS",
    "HOOK",
    "SCRIPT",
    "SCENES",
    "VISUAL_ACTION_DIRECTION",
    "ON_SCREEN_TEXT",
    "TITLE",
    "SECTIONS_DATA_POINTS",
    "VISUAL_STRUCTURE",
    "POST_TEXT",
    "HOOK_OPENING",
    "SETUP",
    "PUNNACLE",
    "VISUAL_CONCEPT",
    "FRAME_SEQUENCE",
    "TEXT",
    "POLL_QUESTION",
}

_SLIDE_MARKER = re.compile(r"SLIDE\s+\d+")
_HEADER = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_ -]{1,40}?)\s*(?::\s*(.*))?$")


def _parse_header(line):
    """Return (KEY, inline value) when the line starts a known field."""
    match = _HEADER.match(line.strip())
    if not match:
        return None

    key = re.sub(r"[-\s]+", " ", match.group(1).strip()).upper()
    key = _ALIASES.get(key, key)

    if key in _KEYS or _SLIDE_MARKER.fullmatch(key):
        return key, (match.group(2) or "").strip()
    return None


def _sections(raw):
    """Split Vera's plain-text output into ordered (key, value) sections.

    A section keeps every following line until the next recognized header, so
    multi-line bodies and captions survive intact.
    """
    sections = []
    current = None

    for line in raw.splitlines():
        parsed = _parse_header(line)
        if parsed:
            key, value = parsed
            current = {"key": key, "value": value, "lines": []}
            sections.append(current)
        elif current is not None:
            stripped = line.strip()
            if stripped:
                current["lines"].append(stripped)

    for section in sections:
        if section["lines"]:
            parts = ([section["value"]] if section["value"] else []) + section["lines"]
            section["value"] = "\n".join(parts).strip()

    return sections


def _flat_fields(raw):
    fields = {}
    for section in _sections(raw):
        fields.setdefault(section["key"], section["value"])
    return fields


def _split_numbered(text, marker):
    """Split "Scene 1: ... Scene 2: ..." / "Frame 1: ..." blocks into items."""
    if not text:
        return []

    pattern = re.compile(r"(?i)\b" + marker + r"\s*\d+\s*[:.)-]\s*")
    matches = list(pattern.finditer(text))
    pieces = []

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        piece = text[match.end():end].strip()
        if piece:
            pieces.append(piece)

    if pieces:
        return pieces

    return [line.strip() for line in text.splitlines() if line.strip()]


def _parse_carousel(raw):
    slides = []
    caption = ""
    hashtags = ""
    current = None

    for section in _sections(raw):
        key = section["key"]

        if _SLIDE_MARKER.fullmatch(key):
            current = {
                "headline": section["value"],
                "subheadline": "",
                "body": "",
                "cta": "",
                "visual_direction": "",
            }
            slides.append(current)
            continue

        if key == "CAPTION":
            caption = section["value"]
            current = None
            continue

        if key == "HASHTAGS":
            hashtags = section["value"]
            current = None
            continue

        if current is None:
            continue

        if key == "HEADLINE":
            current["headline"] = section["value"]
        elif key == "SUB_HEADLINE":
            current["subheadline"] = section["value"]
        elif key == "BODY":
            current["body"] = section["value"]
        elif key == "CTA":
            current["cta"] = section["value"]
        elif key == "VISUAL_DIRECTION":
            current["visual_direction"] = section["value"]

    return slides, caption, hashtags


def _build_copy(raw, fmt):
    """Extract canonical fields from plain text for one format."""
    if fmt == "CAROUSEL":
        slides, caption, hashtags = _parse_carousel(raw)
        return {
            "format": fmt,
            "raw": raw,
            "slides": slides,
            "caption": caption,
            "hashtags": hashtags,
        }

    fields = _flat_fields(raw)

    if fmt == "SINGLE_IMAGE":
        return {
            "format": fmt,
            "raw": raw,
            "headline": fields.get("HEADLINE", ""),
            "supporting_text": fields.get("SUPPORTING_TEXT", ""),
            "visual_concept": fields.get("VISUAL_CONCEPT", ""),
            "cta": fields.get("CTA", ""),
            "caption": fields.get("CAPTION", ""),
            "hashtags": fields.get("HASHTAGS", ""),
        }

    if fmt == "REEL":
        scenes = [
            {"visual_direction": text, "on_screen_text": "", "duration": ""}
            for text in _split_numbered(fields.get("SCENES", ""), "Scene")
        ]
        return {
            "format": fmt,
            "raw": raw,
            "hook": fields.get("HOOK", ""),
            "script": fields.get("SCRIPT", ""),
            "scenes": scenes,
            "visual_action_direction": fields.get("VISUAL_ACTION_DIRECTION", ""),
            "on_screen_text": fields.get("ON_SCREEN_TEXT", ""),
            "cta": fields.get("CTA", ""),
            "caption": fields.get("CAPTION", ""),
            "hashtags": fields.get("HASHTAGS", ""),
        }

    if fmt == "INFOGRAPHIC":
        return {
            "format": fmt,
            "raw": raw,
            "title": fields.get("TITLE", "") or fields.get("HEADLINE", ""),
            "sections_data_points": fields.get("SECTIONS_DATA_POINTS", ""),
            "visual_structure": fields.get("VISUAL_STRUCTURE", ""),
            "cta": fields.get("CTA", ""),
            "caption": fields.get("CAPTION", ""),
            "hashtags": fields.get("HASHTAGS", ""),
        }

    if fmt == "TEXT_POST":
        return {
            "format": fmt,
            "raw": raw,
            "post_text": fields.get("POST_TEXT", ""),
            "hook_opening": fields.get("HOOK_OPENING", ""),
            "cta": fields.get("CTA", ""),
            "caption": fields.get("CAPTION", ""),
            "hashtags": fields.get("HASHTAGS", ""),
        }

    if fmt == "MEME":
        return {
            "format": fmt,
            "raw": raw,
            "setup": fields.get("SETUP", ""),
            "punchline": fields.get("PUNNACLE", "") or fields.get("PUNCHLINE", ""),
            "visual_concept": fields.get("VISUAL_CONCEPT", ""),
            "caption": fields.get("CAPTION", ""),
            "hashtags": fields.get("HASHTAGS", ""),
        }

    if fmt == "STORY_POLL":
        return {
            "format": fmt,
            "raw": raw,
            "frame_sequence": _split_numbered(
                fields.get("FRAME_SEQUENCE", ""), "Frame"
            ),
            "text": fields.get("TEXT", ""),
            "poll": fields.get("POLL_QUESTION", ""),
            "cta": fields.get("CTA", ""),
            "caption": fields.get("CAPTION", ""),
            "hashtags": fields.get("HASHTAGS", ""),
        }

    return {"format": "CAROUSEL", "raw": raw, "slides": []}


def _detect_format(raw):
    upper = raw.upper()
    if "FRAME_SEQUENCE" in upper or "POLL_QUESTION" in upper:
        return "STORY_POLL"
    if "HOOK_OPENING" in upper or "POST_TEXT" in upper:
        return "TEXT_POST"
    if "SECTIONS_DATA_POINTS" in upper or "VISUAL_STRUCTURE" in upper:
        return "INFOGRAPHIC"
    if "PUNNACLE" in upper or "SETUP" in upper:
        return "MEME"
    if "SUPPORTING_TEXT" in upper:
        return "SINGLE_IMAGE"
    if "SCENES" in upper or "HOOK" in upper or "SCRIPT" in upper:
        return "REEL"
    return "CAROUSEL"


def _parse_llm_output(raw, fmt=None, topic=None):
    """Parse Vera's plain-text output into canonical copy for one format."""
    if not raw or not isinstance(raw, str) or not raw.strip():
        return models.fallback_copy(fmt or "CAROUSEL", topic or "")

    fmt = (fmt or _detect_format(raw)).upper()
    if fmt not in SUPPORTED_FORMATS:
        fmt = "CAROUSEL"

    try:
        return models.normalize_copy(_build_copy(raw.strip(), fmt), fmt)
    except (ValueError, TypeError) as exc:
        return models.fallback_copy(fmt, topic or raw.strip()[:80], exc)


def run(topic, fmt="CAROUSEL"):
    """Generate format-aware copy for a topic.

    Args:
        topic: The content topic/idea.
        fmt: The selected format.
    Returns:
        A canonical copy dict (see core/models.py) for the selected format.
    """
    fmt = (fmt or "CAROUSEL").upper()
    if fmt not in SUPPORTED_FORMATS:
        fmt = "CAROUSEL"

    prompt = _build_format_prompt(fmt, topic)

    try:
        raw = generate(prompt)
    except Exception as exc:
        return models.fallback_copy(fmt, topic, exc)

    return _parse_llm_output(raw, fmt, topic)
