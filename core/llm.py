import json
import re

import requests

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


# Mock Vera output, one block per supported format. The mock routes on the
# exact format named in Vera's prompt ("OUTPUT FORMAT - <FORMAT>") because the
# prompt contains the word "caption" for every format; keyword sniffing made
# every format look like TEXT_POST.
_VERA_MOCK = {
    "CAROUSEL": """SLIDE 1
HEADLINE: 7 Kitchen Storage Hacks That Actually Work
SUB_HEADLINE: A place for everything, and everything in its place.
BODY: Small changes to your kitchen storage make daily cooking easier and less stressful.
VISUAL_DIRECTION: Warm, bright kitchen with open modular shelving.

SLIDE 2
HEADLINE: The One Countertop Rule
SUB_HEADLINE: Clear surfaces mean clear minds.
BODY: Keep only daily-use items on your countertop so the space feels calm.
VISUAL_DIRECTION: Minimalist counter with a single wooden chopping board.

SLIDE 3
HEADLINE: Daily 5-Minute Reset
SUB_HEADLINE: A tiny habit with a big payoff.
BODY: Spend five minutes after dinner putting things back where they belong.
VISUAL_DIRECTION: Overhead shot of a clean, organized kitchen island.

CAPTION
A clutter-free kitchen is a happy kitchen. Start with one small change today.
HASHTAGS
#KitchenHacks #HomeOrganization #Vastu #SmartLiving""",

    "SINGLE_IMAGE": """HEADLINE
The One Countertop Rule
SUPPORTING_TEXT
Keep only what you use every day. A clear countertop makes a kitchen feel instantly bigger and calmer.
VISUAL_CONCEPT
Bright, clean kitchen counter with a single wooden cutting board and a small plant.
CTA
Start with one countertop and keep it clear this week.
CAPTION
Clear surfaces, clear mind.
HASHTAGS
#KitchenOrganizing #HomeTips #ClutterFree""",

    "REEL": """HOOK
Stop letting clutter take over your kitchen.
SCRIPT
Define a single storage home for every item. Clear your countertop. Spend five minutes a day resetting. Watch your kitchen breathe again.
SCENES
Scene 1: Cluttered kitchen counter with broken appliances and stacked dishes.
Scene 2: Hands clearing each item into labeled baskets.
Scene 3: Clean, bright countertop with one plant and open shelving.
VISUAL_ACTION_DIRECTION
Before/after split screen showing the transformation from chaos to calm.
ON_SCREEN_TEXT
One home per item. Five minutes a day. Before and after.
CTA
Start with the countertop.
CAPTION
Small storage changes, big calm.
HASHTAGS
#KitchenOrganization #SmallSpace #HomeHacks""",

    "INFOGRAPHIC": """TITLE
Kitchen Organization by the Numbers
SECTIONS_DATA_POINTS
Countertop clear: 90% less visible clutter
Items stored: 12 labeled bins
Daily reset: 5 minutes
VISUAL_STRUCTURE
Left: clean counter scene. Center: bar chart showing 90% storage used. Right: 5-minute reset checklist.
CTA
Download the 5-minute reset checklist.
CAPTION
Data shows a clutter-free kitchen. Apply one change at a time.
HASHTAGS
#KitchenHacks #HomeOrganization #MinimalistKitchen""",

    "TEXT_POST": """POST_TEXT
A clutter-free kitchen is a happy kitchen. Start with one small change today.
Pick one zone, decide a home for every item, and spend five minutes a day resetting.
Consistency beats perfection.
HOOK_OPENING
The fastest way to feel calm at home.
CTA
Pick one zone and start today.
CAPTION
Small changes, big calm.
HASHTAGS
#KitchenHacks #HomeOrganization #Minimalist""",

    "MEME": """SETUP
When you finally organize the kitchen.
PUNNACLE
...and the counter still looks like a war zone.
VISUAL_CONCEPT
A chaotic kitchen island next to a calm, minimalist one.
CAPTION
Organization is a journey, not a destination.
HASHTAGS
#KitchenHacks #HomeLife #Relatable""",

    "STORY_POLL": """FRAME_SEQUENCE
Frame 1: A messy kitchen with a question mark.
Frame 2: A clean kitchen with a checkmark.
TEXT
Which would you choose?
POLL_QUESTION
When was the last time you cleared your kitchen counter?
CTA
Vote below and share your storage hack.
CAPTION
Your countertop says a lot about your home.
HASHTAGS
#KitchenPoll #HomeGoals #OrganizationTips""",
}


def _prompt_format(prompt):
    """Read the exact format name out of Vera's prompt."""
    match = re.search(r"OUTPUT FORMAT\s*-\s*([A-Z_]+)", prompt, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    match = re.search(r"SELECTED FORMAT:\s*([A-Za-z_ ]+)", prompt)
    if match:
        value = match.group(1).strip().upper().replace(" ", "_")
        if value in _VERA_MOCK:
            return value

    return "CAROUSEL"


def generate(prompt):
    # Real API mode only when a key is configured; MOCK_MODE is False only
    # when OPENROUTER_API_KEY is set (see config.py).
    if not MOCK_MODE:
        return _real_generate(prompt)

    p = prompt.lower()

    # --- Vera vs Atlas routing ---
    # Vera's prompt always contains "SELECTED FORMAT:" and "OUTPUT FORMAT";
    # Atlas's prompt is just the topic.
    if "selected format" in p or "output format" in p or "selected topic" in p:
        return _VERA_MOCK.get(_prompt_format(prompt), "[]")

    # --- Atlas: generate a format-aware list of ideas ---
    # Atlas receives just the topic, so the mock triggers on topic content.
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
            "title": f"A 30-Second Walkthrough of {short}",
            "problem": "People want to see the process, not just read about it.",
            "angle": "Show the change step by step in a short video.",
            "format": "REEL",
            "format_reason": "Best because the topic is easier to show than to describe.",
        },
        {
            "title": f"{short} by the Numbers",
            "problem": "Claims without context are hard to trust.",
            "angle": "Turn the key points into one clear visual summary.",
            "format": "INFOGRAPHIC",
            "format_reason": "Best because the topic has several comparable data points.",
        },
        {
            "title": f"A Simple Daily Routine for {short}",
            "problem": "Consistency is harder than knowing what to do.",
            "angle": "Turn the advice into a repeatable daily habit.",
            "format": "TEXT_POST",
            "format_reason": "Best because a routine reads well as a text post.",
        },
        {
            "title": f"When {short} Does Not Go to Plan",
            "problem": "People relate to the gap between expectation and reality.",
            "angle": "Point out the funny side of a common mistake.",
            "format": "MEME",
            "format_reason": "Best because the topic has a relatable, humorous angle.",
        },
        {
            "title": f"Which {short} Habit Works Best for You?",
            "problem": "People like to compare their own habits with others.",
            "angle": "Ask a direct question and invite a vote.",
            "format": "STORY_POLL",
            "format_reason": "Best because the topic invites quick audience participation.",
        },
    ])
