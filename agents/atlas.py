import json
import re

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

# Deterministic format selection rules. Order matters: first match wins.
# (keywords to search in lowercased topic, format)
FORMAT_RULES = [
    # Demonstration / tutorial -> REEL
    (("tutorial", "walk-through", "walkthrough", "how-to", "how to", "step-by-step",
      "demonstration", "demo", "walk", "explain", "why", "journey", "process"), "REEL"),
    # Comparison / data -> INFOGRAPHIC
    (("comparison", "compare", "versus", "vs", "data", "statistic", "chart", "graph",
      "metric", "stats", "pros", "cons", "best"), "INFOGRAPHIC"),
    # Opinion / question -> TEXT_POST
    (("opinion", "question", "thoughts", "hot take", "feedback", "view", "should",
      "think", "feel", "favorite", "what", "how's"), "TEXT_POST"),
    # Engagement / poll -> STORY_POLL
    (("poll", "engagement", "would you", "should i", "ask", "vote", "which"),
     "STORY_POLL"),
    # Meme / relatable / trending -> MEME
    (("relatable", "trend", "trending", "viral", "meme", "funny", "lol", "haha",
      "cringe", "dank"), "MEME"),
    # Multiple actionable points -> CAROUSEL
    (("top", "tips", "ways", "methods", "steps", "guide", "list", "benefits", "reasons",
      "myths"), "CAROUSEL"),
    # One strong tip -> SINGLE_IMAGE
    (("simple", "quick", "easy", "one", "single"), "SINGLE_IMAGE"),
]

# Topics that clearly map to a single-image (one strong tip)
SINGLE_IMAGE_HINTS = (
    "one", "single", "just", "only", "simple", "quick", "easy", "habit",
    "shortcut", "lifehack",
)

# Topics that clearly map to a carousel (multiple points/ideas)
CAROUSEL_HINTS = (
    "top", "best", "tips", "ways", "methods", "steps", "guide", "list",
    "advantages", "disadvantages", "benefits", "reasons", "myths",
)


def select_format(topic: str) -> str:
    """Deterministic format selection based on the topic content."""
    topic_lower = topic.lower()
    for patterns, fmt in FORMAT_RULES:
        if any(p in topic_lower for p in patterns):
            return fmt
    # Default fallback: prefer a tailored hint over CAROUSEL
    if any(w in topic_lower for w in SINGLE_IMAGE_HINTS):
        return "SINGLE_IMAGE"
    if any(w in topic_lower for w in CAROUSEL_HINTS):
        return "CAROUSEL"
    return "CAROUSEL"


def _normalize_idea(raw, topic):
    """Normalize a single parsed idea into the standard structure."""
    if isinstance(raw, str):
        return {
            "title": raw.strip(),
            "problem": "",
            "angle": "",
            "format": select_format(raw),
            "format_reason": "Rule-based fallback (LLM output not structured JSON).",
        }
    if not isinstance(raw, dict):
        return None

    title = str(raw.get("title", "")).strip()
    if not title:
        title = str(raw.get("title_raw", "")).strip() or "(untitled idea)"

    problem = str(raw.get("problem", "")).strip()
    angle = str(raw.get("angle", "")).strip()
    fmt = str(raw.get("format", "")).strip().upper()
    format_reason = str(raw.get("format_reason", "")).strip()

    if not title:
        title = str(raw.get("title_raw", "")).strip() or "(untitled idea)"

    if fmt not in SUPPORTED_FORMATS:
        fmt = select_format(title)
        format_reason = format_reason or "Rule-based fallback"

    return {
        "title": title,
        "problem": problem,
        "angle": angle,
        "format": fmt,
        "format_reason": format_reason,
    }


def _parse_llm_output(raw, topic):
    """Robustly parse Atlas LLM output into a list of idea dicts."""
    if not raw or not isinstance(raw, str):
        return []

    raw = raw.strip()
    if not raw:
        return []

    # --- 1. Try JSON (with optional markdown fences) ---
    try:
        candidate = raw
        if candidate.startswith("```"):
            i = candidate.index("\n")
            candidate = candidate[i + 1:].lstrip()
        if candidate.endswith("```"):
            candidate = candidate[:candidate.rindex("```")].rstrip()
        data = json.loads(candidate)
        if isinstance(data, list):
            return [_normalize_idea(item, topic) for item in data if isinstance(item, (dict, str))]
        if isinstance(data, dict):
            for key in ("ideas", "items", "content", "data"):
                if isinstance(data.get(key), list):
                    return [_normalize_idea(item, topic) for item in data[key]
                            if isinstance(item, (dict, str))]
            return [_normalize_idea(data, topic)]
    except (json.JSONDecodeError, ValueError):
        pass

    # --- 2. Fallback: regex-based plain-text parsing ---
    return _parse_plain_text(raw, topic)


def _parse_plain_text(raw, topic):
    """Fallback parser for mock mode / malformed plain-text output."""
    # Split on numbered items: "1.", "2.", "3)", "1)", etc.
    blocks = re.split(r"\n(?=\d+[\.\)]\s+)", raw)
    ideas = []
    for block in blocks:
        block = re.sub(r"\s+", " ", block).strip()
        if not block:
            continue
        # Strip a leading "1.", "1)", "(1)" style marker
        block = re.sub(r"^\d+[\.\)\)]\s*", "", block).strip()
        if not block:
            continue
        ideas.append({
            "title": block,
            "problem": "",
            "angle": "",
            "format": select_format(block),
            "format_reason": "Rule-based fallback (mock mode plain text).",
        })
    return ideas


def run(topic: str):
    """Generate structured content ideas for a topic, each with a deterministic format."""
    prompt = f"""
You are Atlas, the content-idea research agent for a social media Content Studio.

Topic:
{topic}

Generate exactly 5 strong Instagram content ideas for this topic.

For each idea, provide:
1. Title
2. Audience problem/question it addresses
3. One-line angle
4. Recommended format: CAROUSEL | SINGLE_IMAGE | REEL | INFOGRAPHIC | TEXT_POST | MEME | STORY_POLL
5. format_reason: short explanation (why this format fits)

Rules:
- Practical and useful
- Avoid repetitive ideas
- Do not invent statistics or scientific claims
- Do not assume any particular niche
- Keep each idea concise
- Return ONLY valid JSON: a JSON array of 5 objects, each with keys "title", "problem", "angle", "format", "format_reason".
- Do NOT include any other text, markdown, or explanations.

Example:
[
  {{
    "title": "Start Small",
    "problem": "People feel overwhelmed by big goals.",
    "angle": "Break any goal into a 5-minute first step.",
    "format": "SINGLE_IMAGE",
    "format_reason": "Best because this topic is a single strong tip."
  }},
  ...
]
"""
    raw = generate(prompt)
    ideas = _parse_llm_output(raw, topic)
    # Keep at most 5; drop empty entries; dedupe by lowercase title
    seen = set()
    out = []
    for i in ideas:
        t = i.get("title", "").strip().lower()
        if t and t not in seen:
            seen.add(t)
            out.append(i)
    return out[:5]
