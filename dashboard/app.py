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
    """Serve generated preview assets from allowlisted project folders.

    Allowed locations are ``data/renders/`` (Kite output) and
    ``static/assets/`` (legacy assets). Anything else is rejected so the
    route cannot read arbitrary files.
    """
    project_root = os.path.realpath(BASE_DIR)
    allowed_roots = [
        os.path.realpath(os.path.join(project_root, "data", "renders")),
        os.path.realpath(os.path.join(project_root, "static", "assets")),
    ]

    if not filename or ".." in filename or "\\" in filename:
        return jsonify({"error": "invalid path"}), 400
    if filename.startswith("/") or os.path.isabs(filename) or ":" in filename:
        return jsonify({"error": "invalid path"}), 400

    normalized = filename.replace("\\", "/")

    if normalized.startswith("data/renders/") or normalized.startswith("static/assets/"):
        candidate = os.path.realpath(os.path.join(project_root, normalized))
    else:
        # Legacy callers pass a path relative to static/assets.
        candidate = os.path.realpath(
            os.path.join(project_root, "static", "assets", normalized)
        )

    if not any(
        candidate == root or candidate.startswith(root + os.sep)
        for root in allowed_roots
    ):
        return jsonify({"error": "path outside asset directories"}), 403

    if not os.path.isfile(candidate):
        return jsonify({"error": "not found"}), 404

    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".txt": "text/plain; charset=utf-8",
    }
    ext = os.path.splitext(candidate)[1].lower()
    mime = mime_map.get(ext, "application/octet-stream")

    with open(candidate, "rb") as handle:
        return handle.read(), 200, {"Content-Type": mime}


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
            "Atlas generated " + str(len(ideas)) + " ideas for item " + str(item_id)
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

        # Vera already returns the canonical dict for every format, so Kite
        # gets the dict directly (no lossy re-serialization).
        fmt = item.get("format", "CAROUSEL").upper()
        design_result = kite(item_id, item["copy"], fmt)

        item["design"] = design_result
        item["stage"] = "design"
        item["status"] = "pending_approval"

        add_activity(
            s,
            "Kite rendered " + str(design_result.get("count", 0)) + " assets for item " + str(item_id)
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

        # Write the published snapshot only after the item reaches its final
        # state, so the snapshot is not a stale pre-publish copy.
        item["published"] = True
        item["stage"] = "done"
        item["status"] = "published_local"

        orin(item)

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
            add_activity(s, f"Atlas regenerated {len(ideas)} ideas for item {item_id}")
        elif stage == "copy":
            if not selected_idea or not fmt:
                return jsonify({"error": "cannot regenerate copy: missing selected idea or format"}), 400
            copy_result = vera(selected_idea, fmt)
            item["copy"] = copy_result
            add_activity(s, f"Vera regenerated copy for item {item_id} (reject -> regenerate)")
        elif stage == "design":
            if not item.get("copy"):
                return jsonify({"error": "cannot regenerate design: no copy data"}), 400
            design_result = kite(item_id, item["copy"], fmt or "CAROUSEL")
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
