from flask import Flask, jsonify, request, render_template
import os

# Absolute paths for templates and static folders
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR
)

from core.state import load, save, create_item, add_activity
from agents.atlas import run as atlas
from agents.vera import run as vera
from agents.kite import run as kite
from agents.orin import run as orin


# Single action vocabulary shared with templates/index.html.
# The UI sends exactly these names and the server accepts an action only
# at the stages listed here.
STAGE_ACTIONS = {
    "idea": {"approve_idea", "reject"},
    "idea_review": {"select_idea", "approve_idea", "reject"},
    "copy": {"approve_copy", "reject"},
    "design": {"approve_design", "reject"},
    "publish": {"publish"},
    "done": set(),
}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def state():
    return jsonify(load())


@app.get("/api/asset/<path:filename>")
def serve_asset(filename):
    """Serve local preview assets with path validation.

    Only files under the project static/assets directory are accessible.
    Avoids file:// URLs in the browser.
    """
    # Define the allowed assets directory
    ASSETS_DIR = os.path.join(BASE_DIR, "static", "assets")

    # Prevent directory traversal
    if ".." in filename or filename.startswith("/") or "\\" in filename:
        return jsonify({"error": "invalid path"}), 400

    safe_path = os.path.normpath(filename)

    full_path = os.path.join(ASSETS_DIR, safe_path)

    # Resolve to absolute path and verify it is inside ASSETS_DIR
    try:
        real_path = os.path.realpath(full_path)
        real_assets = os.path.realpath(ASSETS_DIR)
        if not real_path.startswith(real_assets + os.sep) and real_path != real_assets:
            return jsonify({"error": "path outside assets directory"}), 403
    except Exception:
        return jsonify({"error": "invalid path"}), 400

    if not os.path.exists(real_path):
        return jsonify({"error": "not found"}), 404

    if not os.path.isfile(real_path):
        return jsonify({"error": "not a file"}), 404

    # Guess content type from extension
    ext = os.path.splitext(safe_path)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }
    mime = mime_map.get(ext, "application/octet-stream")

    with open(real_path, "rb") as f:
        return f.read(), 200, {"Content-Type": mime}


@app.post("/api/idea")
def idea():
    topic = request.json.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "topic required"}), 400
    item = create_item(topic)
    return jsonify(item)


@app.post("/api/action/<int:item_id>")
def action(item_id):
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")

    s = load()

    item = next(
        (x for x in s["items"] if x["id"] == item_id),
        None
    )

    if not item:
        return jsonify({"error": "not found"}), 404

    stage = item.get("stage", "idea")
    if action not in STAGE_ACTIONS.get(stage, set()):
        return jsonify({
            "error": "action %r is not allowed at stage %r" % (action, stage)
        }), 400


    # ---------------------------------------------------------
    # IDEA APPROVAL
    # ---------------------------------------------------------
    if action == "approve_idea":

        ideas = atlas(item["topic"])

        item["ideas"] = ideas
        item["stage"] = "idea_review"
        item["status"] = "pending_approval"

        add_activity(
            s,
            "Atlas generated 5 ideas for item " + str(item_id)
        )

    # ---------------------------------------------------------
    # HUMAN SELECTS ONE ATLAS IDEA
    # ---------------------------------------------------------
    elif action == "select_idea":

        selected = (payload.get("selected_idea") or "").strip()

        if not selected:
            return jsonify({"error": "idea required"}), 400

        item["selected_idea"] = selected

        # Extract the format from the selected idea
        selected_format = "CAROUSEL"
        if item.get("ideas"):
            for idea in item["ideas"]:
                if isinstance(idea, dict) and idea.get("title") == selected:
                    selected_format = idea.get("format", "CAROUSEL")
                    break
                elif isinstance(idea, dict) and selected.lower() in idea.get("title", "").lower():
                    selected_format = idea.get("format", "CAROUSEL")
                    break

        item["format"] = selected_format
        item["copy"] = vera(selected, selected_format)

        item["stage"] = "copy"
        item["status"] = "pending_approval"

        add_activity(
            s,
            f"Human selected Atlas idea for item {item_id} (format: {selected_format}); Vera generated {selected_format.lower()}"
        )

    # ---------------------------------------------------------
    # COPY APPROVAL
    # ---------------------------------------------------------
    elif action == "approve_copy":

        # For formats that kite renders from structured dict (TEXT_POST,
        # REEL, INFOGRAPHIC, MEME, STORY_POLL) pass the dict straight through.
        # For CAROUSEL we convert to the old string format (SLIDE 1..5)
        # so Kite's string path can extract slides.
        fmt = item.get("format", "CAROUSEL").upper()
        if fmt == "CAROUSEL":
            copy_text = _format_copy_for_kite(item["copy"], fmt)
            design_result = kite(item_id, copy_text, fmt)
        else:
            design_result = kite(item_id, item["copy"], fmt)

        item["design"] = design_result
        item["stage"] = "design"
        item["status"] = "pending_approval"

        add_activity(
            s,
            "Kite rendered " + str(design_result.get("count", 0)) + " slides and uploaded them to ImgBB for item " + str(item_id)
        )

    # ---------------------------------------------------------
    # DESIGN APPROVAL
    # ---------------------------------------------------------
    elif action == "approve_design":

        item["stage"] = "publish"
        item["status"] = "pending_approval"

        add_activity(
            s,
            "Item " + str(item_id) + " ready for final publish approval"
        )


    # ---------------------------------------------------------
    # FINAL PUBLISH
    # ---------------------------------------------------------
    elif action == "publish":

        orin(item)

        item["published"] = True
        item["stage"] = "done"
        item["status"] = "published_local"

        add_activity(
            s,
            "Item " + str(item_id) + " saved as local publish package"
        )


    # ---------------------------------------------------------
    # REJECT -> REGENERATE the current stage
    # ---------------------------------------------------------
    elif action == "reject":
        stage = item.get("stage")
        topic = item.get("topic")
        fmt = item.get("format")
        selected_idea = item.get("selected_idea")

        if stage in ("idea", "idea_review"):
            ideas = atlas(topic)
            item["ideas"] = ideas
            add_activity(s, f"Atlas regenerated 5 ideas for item {item_id}")
        elif stage == "copy":
            if not selected_idea or not fmt:
                return jsonify({"error": "cannot regenerate copy: missing selected idea or format"}), 400
            copy_result = vera(selected_idea, fmt)
            item["copy"] = copy_result
            add_activity(s, f"Vera regenerated copy for item {item_id} (reject -> regenerate)")
        elif stage == "design":
            if not item.get("copy"):
                return jsonify({"error": "cannot regenerate design: no copy data"}), 400
            copy_text = _format_copy_for_kite(item["copy"], fmt or "CAROUSEL")
            design_result = kite(item_id, copy_text, fmt or "CAROUSEL")
            item["design"] = design_result
            add_activity(s, f"Kite regenerated design for item {item_id} (reject -> regenerate)")
        else:
            return jsonify({"error": "cannot regenerate at stage " + repr(stage)}), 400

        save(s)
        return jsonify(item)

    else:
        return jsonify({"error": "unknown action"}), 400


    save(s)

    return jsonify(item)


@app.get("/api/item/<int:item_id>")
def get_item(item_id):
    s = load()
    item = next((x for x in s["items"] if x["id"] == item_id), None)
    if not item:
        return jsonify({"error": "not found"}), 404
    return jsonify(item)


def _format_copy_for_kite(copy_data, fmt="CAROUSEL"):
    """Convert Vera's new structured copy format to old string format for Kite.

    Kite's _extract_slides() expects SLIDE 1..5 markers in plain text.
    This helper converts the new structured dict back to that format.
    """
    if not copy_data:
        return ""

    # If it's already a string, return as-is
    if isinstance(copy_data, str):
        return copy_data

    # If it's a dict with structured fields, convert to string format
    if isinstance(copy_data, dict):
        fmt = fmt.upper()
        if fmt == "CAROUSEL":
            lines = []
            slides = copy_data.get("slides", [])
            for i, slide in enumerate(slides, 1):
                # slide can be a string or a dict
                if isinstance(slide, dict):
                    headline = slide.get("headline", "") or slide.get("slide_1_headline", "")
                    subheadline = slide.get("subheadline", "") or slide.get("slide_1_subheadline", "")
                    body = slide.get("body", "") or slide.get("slide_1_body", "")
                    cta = slide.get("cta", "") or slide.get("slide_5_cta", "")
                    visual = slide.get("visual_direction", "") or slide.get("slide_1_direction", "")
                else:
                    # slide is a string - use first line as headline
                    slide_lines = str(slide).split("\n")
                    headline = slide_lines[0].strip() if slide_lines else ""
                    subheadline = ""
                    body = ""
                    cta = ""
                    visual = ""
                
                lines.append(f"SLIDE {i}")
                lines.append(f"Headline: {headline}")
                if subheadline:
                    lines.append(f"Sub-headline: {subheadline}")
                if body:
                    lines.append(f"Body: {body}")
                if visual:
                    lines.append(f"Visual direction: {visual}")
                lines.append("")

            caption = copy_data.get("caption", "")
            if caption:
                lines.append("CAPTION")
                lines.append(caption)
                lines.append("")

            hashtags = copy_data.get("hashtags", "")
            if hashtags:
                lines.append("HASHTAGS")
                lines.append(hashtags)

            return "\n".join(lines)

        elif fmt == "REEL":
            hook = copy_data.get("hook", "")
            script = copy_data.get("script", "")
            scenes = copy_data.get("scenes", [])
            direction = copy_data.get("visual_action_direction", "")
            text = copy_data.get("on_screen_text", "")
            cta = copy_data.get("cta", "")
            caption = copy_data.get("caption", "")
            hashtags = copy_data.get("hashtags", "")

            lines = []
            lines.append("HOOK")
            lines.append(hook)
            lines.append("")
            lines.append("SCRIPT")
            lines.append(script)
            lines.append("")
            lines.append("SCENES")
            for i, scene in enumerate(scenes, 1):
                lines.append(f"Scene {i}: {scene}")
            lines.append("")
            lines.append("VISUAL_ACTION_DIRECTION")
            lines.append(direction)
            lines.append("")
            lines.append("ON_SCREEN_TEXT")
            lines.append(text)
            lines.append("")
            lines.append("CTA")
            lines.append(cta)
            lines.append("")
            lines.append("CAPTION")
            lines.append(caption)
            lines.append("")
            lines.append("HASHTAGS")
            lines.append(hashtags)
            return "\n".join(lines)

        elif fmt == "SINGLE_IMAGE":
            headline = copy_data.get("headline", "")
            supporting = copy_data.get("supporting_text", "")
            concept = copy_data.get("visual_concept", "")
            cta = copy_data.get("cta", "")
            caption = copy_data.get("caption", "")
            hashtags = copy_data.get("hashtags", "")

            lines = []
            lines.append("HEADLINE")
            lines.append(headline)
            lines.append("")
            lines.append("SUPPORTING_TEXT")
            lines.append(supporting)
            lines.append("")
            lines.append("VISUAL_CONCEPT")
            lines.append(concept)
            lines.append("")
            lines.append("CTA")
            lines.append(cta)
            lines.append("")
            lines.append("CAPTION")
            lines.append(caption)
            lines.append("")
            lines.append("HASHTAGS")
            lines.append(hashtags)
            return "\n".join(lines)

        elif fmt == "INFOGRAPHIC":
            headline = copy_data.get("headline", "") or copy_data.get("title", "")
            sections = copy_data.get("sections_data_points", "")
            structure = copy_data.get("visual_structure", "")
            cta = copy_data.get("cta", "")
            caption = copy_data.get("caption", "")
            hashtags = copy_data.get("hashtags", "")

            lines = []
            lines.append("TITLE")
            lines.append(headline)
            lines.append("")
            lines.append("SECTIONS_DATA_POINTS")
            lines.append(sections)
            lines.append("")
            lines.append("VISUAL_STRUCTURE")
            lines.append(structure)
            lines.append("")
            lines.append("CTA")
            lines.append(cta)
            lines.append("")
            lines.append("CAPTION")
            lines.append(caption)
            lines.append("")
            lines.append("HASHTAGS")
            lines.append(hashtags)
            return "\n".join(lines)

        elif fmt == "TEXT_POST":
            post = copy_data.get("post_text", "")
            hook = copy_data.get("hook_opening", "")
            cta = copy_data.get("cta", "")
            caption = copy_data.get("caption_text", "") or copy_data.get("caption", "")
            hashtags = copy_data.get("hashtags", "")

            lines = []
            lines.append("POST_TEXT")
            lines.append(post)
            lines.append("")
            lines.append("HOOK_OPENING")
            lines.append(hook)
            lines.append("")
            lines.append("CTA")
            lines.append(cta)
            lines.append("")
            lines.append("CAPTION")
            lines.append(caption)
            lines.append("")
            lines.append("HASHTAGS")
            lines.append(hashtags)
            return "\n".join(lines)

        elif fmt == "MEME":
            setup = copy_data.get("setup", "")
            punchline = copy_data.get("punchline", "")
            concept = copy_data.get("visual_concept", "")
            caption = copy_data.get("caption_text", "")
            hashtags = copy_data.get("hashtags", "")

            lines = []
            lines.append("SETUP")
            lines.append(setup)
            lines.append("")
            lines.append("PUNNACLE")
            lines.append(punchline)
            lines.append("")
            lines.append("VISUAL_CONCEPT")
            lines.append(concept)
            lines.append("")
            lines.append("CAPTION")
            lines.append(caption)
            lines.append("")
            lines.append("HASHTAGS")
            lines.append(hashtags)
            return "\n".join(lines)

        elif fmt == "STORY_POLL":
            frames = copy_data.get("frame_sequence", [])
            text = copy_data.get("text", "")
            poll = copy_data.get("poll_question", copy_data.get("polls", ""))
            cta = copy_data.get("cta", "")
            caption = copy_data.get("caption", "")
            hashtags = copy_data.get("hashtags", "")

            lines = []
            lines.append("FRAME_SEQUENCE")
            for i, frame in enumerate(frames, 1):
                lines.append(f"Frame {i}: {frame}")
            lines.append("")
            lines.append("TEXT")
            lines.append(text)
            lines.append("")
            lines.append("POLL_QUESTION")
            lines.append(poll)
            lines.append("")
            lines.append("CTA")
            lines.append(cta)
            lines.append("")
            lines.append("CAPTION")
            lines.append(caption)
            lines.append("")
            lines.append("HASHTAGS")
            lines.append(hashtags)
            return "\n".join(lines)

    return str(copy_data or "")

