

from core.llm import generate


SUPPORTED_FORMATS = [
    "CAROUSEL",
    "SINGLE_IMAGE",
    "REEL",
    "INFOGRAPHIC",
    "TEXT_POST",
    "MEME",
    "STORY_POLL",
]


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


def _parse_llm_output(raw):
    """Safely parse LLM output. Returns a dict with the recognized fields."""
    if not raw or not isinstance(raw, str):
        return {"raw": raw or "", "format": "CAROUSEL"}

    raw = raw.strip()
    if not raw:
        return {"raw": raw, "format": "CAROUSEL"}

    result = {
        "raw": raw,
        "format": "CAROUSEL",
        "slides": [],
        "hook": "",
        "script": "",
        "scenes": [],
        "visual_action_direction": "",
        "on_screen_text": "",
        "cta": "",
        "caption": "",
        "headline": "",
        "supporting_text": "",
        "visual_concept": "",
        "doi": "",
        "setup": "",
        "punchline": "",
        "caption_text": "",
        "frame_sequence": [],
        "poll_question": "",
        "sections_data_points": "",
        "visual_structure": "",
        "post_text": "",
        "hook_opening": "",
        "hashtags": "",
    }

    fmt = "CAROUSEL"
    # Check for format-specific markers (more specific patterns first)
    if "FRAME_SEQUENCE" in raw.upper() or "POLL_QUESTION" in raw.upper():
        fmt = "STORY_POLL"
    elif "HOOK_OPENING" in raw.upper() or "POST_TEXT" in raw.upper():
        fmt = "TEXT_POST"
    elif "SECTIONS_DATA_POINTS" in raw.upper() or "VISUAL_STRUCTURE" in raw.upper():
        fmt = "INFOGRAPHIC"
    elif "SETUP" in raw.upper() or "PUNNACLE" in raw.upper():
        fmt = "MEME"
    elif "HEADLINE" in raw.upper() and "SUPPORTING" in raw.upper():
        fmt = "SINGLE_IMAGE"
    elif "HOOK" in raw.upper() or "SCRIPT" in raw.upper():
        fmt = "REEL"
    elif "SLIDE" in raw.upper() or "HEADLINE" in raw.upper():
        fmt = "CAROUSEL"

    result["format"] = fmt

    if fmt == "CAROUSEL":
        _extract_carousel(raw, result)
    elif fmt == "REEL":
        _extract_reel(raw, result)
    elif fmt == "SINGLE_IMAGE":
        _extract_single_image(raw, result)
    elif fmt == "INFOGRAPHIC":
        _extract_infographic(raw, result)
    elif fmt == "TEXT_POST":
        _extract_text_post(raw, result)
    elif fmt == "MEME":
        _extract_meme(raw, result)
    elif fmt == "STORY_POLL":
        _extract_story_poll(raw, result)

    return result


def _extract_carousel(raw, result):
    import re
    slide_pattern = r"SLIDE\s*(\d+)[^\n]*\n(.*?)(?=SLIDE\s*\d+|\nCAPTION\n|$)"
    matches = re.findall(slide_pattern, raw, re.DOTALL | re.IGNORECASE)
    for i, (num, slide_text) in enumerate(matches, 1):
        slide_text = slide_text.strip()
        result["slides"].append(slide_text)
        headline = re.search(r"HEADLINE:\s*(.+?)(?=\n|$)", slide_text, re.IGNORECASE | re.DOTALL)
        if headline:
            result[f"slide_{i}_headline"] = headline.group(1).strip()
        body = re.search(r"BODY:\s*(.+?)(?=\n|$)", slide_text, re.IGNORECASE | re.DOTALL)
        if body:
            result[f"slide_{i}_body"] = body.group(1).strip()
        direction = re.search(r"VISUAL DIRECTION:\s*(.+?)(?=\n|$)", slide_text, re.IGNORECASE | re.DOTALL)
        if direction:
            result[f"slide_{i}_direction"] = direction.group(1).strip()

    if not result["slides"]:
        result["slides"] = [raw]


def _extract_reel(raw, result):
    import re
    if hook := re.search(r"HOOK:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["hook"] = hook.group(1).strip()
    if script := re.search(r"SCRIPT:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["script"] = script.group(1).strip()
    if scenes := re.findall(r"SCENES?\s*\n(.+?)(?=\n|$)", raw, re.IGNORECASE):
        result["scenes"] = [s.strip() for s in scenes]
    if direction := re.search(r"VISUAL_ACTION_DIRECTION:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["visual_action_direction"] = direction.group(1).strip()
    if text := re.search(r"ON_SCREEN_TEXT:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["on_screen_text"] = text.group(1).strip()
    if cta := re.search(r"CTA:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["cta"] = cta.group(1).strip()
    if caption := re.search(r"CAPTION:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["caption"] = caption.group(1).strip()
    if hashtags := re.search(r"HASHTAGS:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["hashtags"] = hashtags.group(1).strip()


def _extract_single_image(raw, result):
    import re
    if headline := re.search(r"HEADLINE:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["headline"] = headline.group(1).strip()
    if supporting := re.search(r"SUPPORTING_TEXT:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["supporting_text"] = supporting.group(1).strip()
    if concept := re.search(r"VISUAL_CONCEPT:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["visual_concept"] = concept.group(1).strip()
    if cta := re.search(r"CTA:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["cta"] = cta.group(1).strip()
    if caption := re.search(r"CAPTION:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["caption"] = caption.group(1).strip()
    if hashtags := re.search(r"HASHTAGS:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["hashtags"] = hashtags.group(1).strip()


def _extract_infographic(raw, result):
    import re
    if title := re.search(r"TITLE:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["headline"] = title.group(1).strip()
    if sections := re.search(r"SECTIONS_DATA_POINTS:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["sections_data_points"] = sections.group(1).strip()
    if structure := re.search(r"VISUAL_STRUCTURE:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["visual_structure"] = structure.group(1).strip()
    if cta := re.search(r"CTA:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["cta"] = cta.group(1).strip()
    if caption := re.search(r"CAPTION:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["caption"] = caption.group(1).strip()
    if hashtags := re.search(r"HASHTAGS:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["hashtags"] = hashtags.group(1).strip()


def _extract_text_post(raw, result):
    import re
    if post := re.search(r"POST_TEXT:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["post_text"] = post.group(1).strip()
    if hook := re.search(r"HOOK_OPENING:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["hook_opening"] = hook.group(1).strip()
    if cta := re.search(r"CTA:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["cta"] = cta.group(1).strip()
    if caption := re.search(r"CAPTION:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["caption_text"] = caption.group(1).strip()
    if hashtags := re.search(r"HASHTAGS:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["hashtags"] = hashtags.group(1).strip()


def _extract_meme(raw, result):
    import re
    if setup := re.search(r"SETUP:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["setup"] = setup.group(1).strip()
    if punchline := re.search(r"PUNNACLE:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["punchline"] = punchline.group(1).strip()
    if concept := re.search(r"VISUAL_CONCEPT:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["visual_concept"] = concept.group(1).strip()
    if caption := re.search(r"CAPTION:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["caption_text"] = caption.group(1).strip()
    if hashtags := re.search(r"HASHTAGS:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["hashtags"] = hashtags.group(1).strip()


def _extract_story_poll(raw, result):
    import re
    if frames := re.findall(r"FRAME_SEQUENCE:\s*\n(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["frame_sequence"] = [f.strip() for f in frames]
    if text := re.search(r"TEXT:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["text"] = text.group(1).strip()
    if poll := re.search(r"POLL_QUESTION:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["polls"] = poll.group(1).strip()
    if cta := re.search(r"CTA:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["cta"] = cta.group(1).strip()
    if caption := re.search(r"CAPTION:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["caption"] = caption.group(1).strip()
    if hashtags := re.search(r"HASHTAGS:\s*(.+?)(?=\n|$)", raw, re.IGNORECASE | re.DOTALL):
        result["hashtags"] = hashtags.group(1).strip()


def run(topic, fmt="CAROUSEL"):
    """Generate format-aware copy for a topic.

    Args:
        topic: The content topic/idea.
        fmt: The selected format.
    Returns:
        A dict with format-specific structured output.
    """
    fmt = (fmt or "CAROUSEL").upper()
    if fmt not in SUPPORTED_FORMATS:
        fmt = "CAROUSEL"

    prompt = _build_format_prompt(fmt, topic)

    try:
        raw = generate(prompt)
        return _parse_llm_output(raw)
    except Exception as e:
        return {
            "raw": topic,
            "format": fmt,
            "slides": [topic],
            "caption": "Generated content (mock mode). Error: " + str(e),
            "hashtags": "#content #socialmedia",
        }


