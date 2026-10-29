import requests
import json
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL, MOCK_MODE


def _real_generate(prompt):
    """Call OpenRouter's chat-completions endpoint and return the text."""
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["choices"][0]["message"]["content"]


def generate(prompt):
    # Real API mode only when a key is configured; MOCK_MODE is False only
    # when OPENROUTER_API_KEY is set (see config.py).
    if not MOCK_MODE:
        return _real_generate(prompt)

    p = prompt.lower()

    # --- Vera vs Atlas routing ---
    # Vera's prompt always contains "SELECTED FORMAT:" and "OUTPUT FORMAT"
    # Atlas's prompt is just the topic (e.g. "Generate 5 ideas for this topic. Topic: X.")
    if "selected format" in p or "output format" in p or "selected topic" in p:
        # --- Vera: generate format-specific mock copy ---
        # Check more specific markers first to avoid misclassifying
        # (e.g. CAROUSEL output contains "caption" which matches TEXT_POST).
        if "slides" in p or "carousel" in p:
            return (
                "SLIDE 1\n"
                "HEADLINE: 7 Kitchen Storage Hacks That Actually Work\n"
                "SUB_HEADLINE: A place for everything, and everything in its place.\n"
                "BODY: Small changes to your kitchen storage make daily cooking easier and less stressful.\n"
                "VISUAL_DIRECTION: Warm, bright kitchen with open modular shelving.\n"
                "\n"
                "SLIDE 2\n"
                "HEADLINE: The One Countertop Rule\n"
                "SUB_HEADLINE: Clear surfaces mean clear minds.\n"
                "BODY: Keep only daily-use items on your countertop so the space feels calm.\n"
                "VISUAL_DIRECTION: Minimalist counter with a single wooden chopping board.\n"
                "\n"
                "SLIDE 3\n"
                "HEADLINE: Daily 5-Minute Reset\n"
                "SUB_HEADLINE: A tiny habit with a big payoff.\n"
                "BODY: Spend five minutes after dinner putting things back where they belong.\n"
                "VISUAL_DIRECTION: Overhead shot of a clean, organized kitchen island.\n"
                "\n"
                "CAPTION:\n"
                "A clutter-free kitchen is a happy kitchen. Start with one small change today.\n"
                "#KitchenHacks #HomeOrganization #Vastu #SmartLiving"
            )

        if "text" in p or "post" in p or "caption" in p:
            return (
                "POST_TEXT: A clutter-free kitchen is a happy kitchen. Start with one small change today. Pick one zone, decide a home for every item, and spend five minutes a day resetting. Consistency beats perfection.\n"
                "HOOK_OPENING: The fastest way to feel calm at home.\n"
                "CTA: Pick one zone and start today.\n"
                "CAPTION: Small changes, big calm. #KitchenHacks #HomeOrganization #Minimalist"
            )

        if "single" in p:
            return (
                "HEADLINE: The One Countertop Rule\n"
                "SUPPORTING_TEXT: Keep only what you use every day. A clear countertop makes a kitchen feel instantly bigger and calmer.\n"
                "VISUAL_CONCEPT: Bright, clean kitchen counter with a single wooden cutting board and a small plant.\n"
                "CTA: Start with one countertop and keep it clear this week.\n"
                "CAPTION: Clear surfaces, clear mind. #KitchenOrganizing #HomeTips #ClutterFree"
            )

        if "reel" in p or "video" in p:
            return (
                "HOOK: Stop letting clutter take over your kitchen.\n"
                "SCRIPT: Define a single storage home for every item. Open your countertop. Spend five minutes a day resetting. Watch your kitchen breathe again.\n"
                "SCENES: Scene 1: Cluttered kitchen counter with broken appliances and stacked dishes. Scene 2: Hands clearing each item into labeled baskets. Scene 3: Clean, bright countertop with one plant and open shelving.\n"
                "VISUAL_ACTION_DIRECTION: Before/after split screen showing the transformation from chaos to calm.\n"
                "ON_SCREEN_TEXT: One home per item. Five minutes a day. Before and after.\n"
                "CTA: Start with the countertop.\n"
                "CAPTION: Small storage changes, big calm. #KitchenOrganization #SmallSpace #HomeHacks"
            )

        if "infographic" in p or "data" in p or "chart" in p:
            return (
                "TITLE: Kitchen Organization by the Numbers\n"
                "SECTIONS_DATA_POINTS: Countertop clear: Yes. Items stored: 90. Daily reset: 5 min. Open shelving: 12 bins. Clutter-free routines: Daily.\n"
                "VISUAL_STRUCTURE: Left: clean counter scene. Center: bar chart showing 90% storage used. Right: 5-minute reset checklist.\n"
                "CTA: Download the 5-minute reset checklist.\n"
                "CAPTION: Data shows a clutter-free kitchen. Apply one change at a time.\n"
                "HASHTAGS: #KitchenHacks #HomeOrganization #MinimalistKitchen"
            )

        if "meme" in p:
            return (
                "SETUP: When you finally organize the kitchen.\n"
                "PUNNACLE: ...and the counter still looks like a war zone.\n"
                "VISUAL_CONCEPT: A chaotic kitchen island next to a calm, minimalist one.\n"
                "CAPTION: Organization is a journey, not a destination.\n"
                "HASHTAGS: #KitchenHacks #HomeLife #Relatable"
            )

        if "story" in p or "poll" in p:
            return (
                "FRAME_SEQUENCE: Frame 1: A messy kitchen with a question mark. Frame 2: A clean kitchen with a checkmark.\n"
                "TEXT: Which would you choose?\n"
                "POLL_QUESTION: When was the last time you cleared your kitchen counter?\n"
                "CTA: Vote below and share your storage hack.\n"
                "CAPTION: Your countertop says a lot about your home.\n"
                "HASHTAGS: #KitchenPoll #HomeGoals #OrganizationTips"
            )

        return "[]"

    # --- Atlas: generate format-aware list of ideas ---
    # Atlas receives just the topic (e.g. "Vastu tips for home"), so the mock
    # must trigger based on the topic content, not a command phrase.
    if "vastu" in p or "home" in p or "living" in p or "space" in p:
        return json.dumps([
            {
                "title": "5 Simple Vastu Changes You Can Make Today",
                "problem": "People feel overwhelmed by big home improvement goals.",
                "angle": "Break any goal into a 5-minute first step.",
                "format": "CAROUSEL",
                "format_reason": "Best because this topic is a simple list of practical tips.",
            },
            {
                "title": "Common Vastu Mistakes in the Entrance",
                "problem": "Entrances become cluttered without people noticing.",
                "angle": "Your entrance sets the energy for the whole home.",
                "format": "SINGLE_IMAGE",
                "format_reason": "Best because this topic is a single strong tip.",
            },
            {
                "title": "Easy Vastu Tips for a Positive Living Space",
                "problem": "Small habits can create a calmer home.",
                "angle": "Start with one change this week and build from there.",
                "format": "TEXT_POST",
                "format_reason": "Best because this topic shares a quick actionable routine.",
            },
        ])
    if "kitchen" in p or "organization" in p or "storage" in p:
        return json.dumps([
            {
                "title": "7 Kitchen Storage Hacks That Actually Work",
                "problem": "Kitchens become cluttered and hard to navigate.",
                "angle": "A place for everything and everything in its place.",
                "format": "CAROUSEL",
                "format_reason": "Best because this topic is a straightforward list of hacks.",
            },
            {
                "title": "The One Countertop Rule Every Home Needs",
                "problem": "Countertops become unusable when cluttered.",
                "angle": "Keep only daily-use items on the countertop.",
                "format": "SINGLE_IMAGE",
                "format_reason": "Best because this topic is a single strong clear rule.",
            },
            {
                "title": "Daily Kitchen Routines That Keep Clutter Away",
                "problem": "Small messes pile up into big clutter over time.",
                "angle": "Install a 5-minute reset routine every evening.",
                "format": "TEXT_POST",
                "format_reason": "Best because this topic shares a quick actionable routine.",
            },
        ])

    # Generic fallback so any new topic can still move through the pipeline
    # in mock mode instead of producing zero ideas.
    topic = "your topic"
    lines = prompt.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() == "topic:" and index + 1 < len(lines):
            candidate = lines[index + 1].strip()
            if candidate:
                topic = candidate
            break

    short = topic[:50].rstrip(" .")
    return json.dumps([
        {
            "title": f"5 Practical Tips for {short}",
            "problem": "People want a simple starting point.",
            "angle": "Break the topic into five small, actionable steps.",
            "format": "CAROUSEL",
            "format_reason": "Best because the topic works as a short list of tips.",
        },
        {
            "title": f"The One Rule That Matters for {short}",
            "problem": "Too many options make it hard to begin.",
            "angle": "Focus on the single highest-impact change.",
            "format": "SINGLE_IMAGE",
            "format_reason": "Best because one strong rule fits a single image.",
        },
        {
            "title": f"A Simple Daily Routine for {short}",
            "problem": "Consistency is harder than knowing what to do.",
            "angle": "Turn the advice into a repeatable daily habit.",
            "format": "TEXT_POST",
            "format_reason": "Best because a routine reads well as a text post.",
        },
    ])
