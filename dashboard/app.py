from flask import Flask, jsonify, request, render_template, redirect
import hmac
import os

from config import ACCESS_TOKEN, MOCK_MODE

# Absolute paths for templates and static folders
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR
)
app.config["MOCK_MODE"] = MOCK_MODE
app.config["ACCESS_TOKEN"] = ACCESS_TOKEN


ALLOWED_FETCH_SITES = {"same-origin", "same-site", "none"}


@app.before_request
def guard_request():
    """Shared-token auth plus same-origin JSON checks for mutating requests."""
    token = app.config.get("ACCESS_TOKEN") or ""
    if token:
        supplied = (
            request.headers.get("X-Content-Studio-Token")
            or request.cookies.get("cs_token")
            or request.args.get("token")
        )
        if not supplied or not hmac.compare_digest(str(supplied), token):
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return (
                "Unauthorized. Open /?token=<CONTENT_STUDIO_TOKEN> once to set "
                "the access cookie.",
                401,
            )
        if request.args.get("token") and request.method == "GET":
            response = redirect("/")
            response.set_cookie(
                "cs_token",
                token,
                httponly=True,
                samesite="Strict",
                secure=request.is_secure,
            )
            return response

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        # A cross-site HTML form cannot send application/json, so requiring it
        # blocks the classic CSRF post. Empty bodies stay allowed so validation
        # errors surface from the route instead of the guard.
        if request.content_length and not request.is_json:
            return jsonify({
                "error": "content-type must be application/json"
            }), 415

        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
            return jsonify({"error": "cross-origin request blocked"}), 403

        fetch_site = request.headers.get("Sec-Fetch-Site")
        if fetch_site and fetch_site not in ALLOWED_FETCH_SITES:
            return jsonify({"error": "cross-site request blocked"}), 403

    return None


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
    )
    return response


from core.state import load, save, create_item, add_activity, locked
from core.state import DATA as DATA_ROOT
from core.models import SUPPORTED_FORMATS
from core import settings as settings_store
from core import providers as provider_adapter
from core.llm import LLMError
from agents.atlas import run as atlas
from agents.vera import run as vera
from agents.kite import run as kite
from agents.orin import run as orin, PublishError

MAX_TOPIC_LENGTH = 300


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


COMING_SOON_PAGES = {
    "content-studio": (
        "Content Studio",
        "Plan and produce a piece of content end to end",
        "This workspace will combine idea generation, copy, design, and "
        "publishing for a single item in one view.",
    ),
    "ideas": (
        "Ideas",
        "Browse and organise generated ideas",
        "This page will collect ideas across items so they can be filtered, "
        "favourited, and turned into content later.",
    ),
    "pipeline": (
        "Content Pipeline",
        "Track every item across the approval gates",
        "This page will show the full pipeline as a board, including stalled "
        "items and stage history.",
    ),
    "assets": (
        "Assets",
        "Review generated images and text packages",
        "This page will provide an asset library with previews, sizes, and the "
        "item each file belongs to.",
    ),
    "projects": (
        "Projects",
        "Group content into campaigns and projects",
        "This page will let multiple items share a brief, schedule, and "
        "publishing target.",
    ),
    "analytics": (
        "Analytics",
        "Measure output and approval throughput",
        "This page will report counts, cycle time, and publishing activity from "
        "the local pipeline data.",
    ),
}


def _coming_soon(key):
    title, subtitle, body = COMING_SOON_PAGES[key]
    return render_template(
        "coming_soon.html",
        active=key,
        page_title=title,
        page_subtitle=subtitle,
        page_body=body,
    )


@app.get("/")
def index():
    return render_template("index.html", active="dashboard")


@app.get("/settings")
def settings_page():
    try:
        mode = settings_store.mode_info()
    except settings_store.SettingsError as exc:
        mode = {"mode": "error", "reason": str(exc)}
    return render_template("settings.html", active="settings", mode=mode)


@app.errorhandler(LLMError)
def handle_llm_error(exc):
    """A provider failure is a clear 502; the item is left untouched."""
    return jsonify({"error": str(exc)}), 502


@app.get("/api/settings/providers")
def list_providers():
    try:
        return jsonify({
            "providers": settings_store.list_providers(),
            "mode": settings_store.mode_info(),
        })
    except settings_store.SettingsError as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/settings/providers")
def add_provider():
    payload = request.get_json(silent=True) or {}
    try:
        provider = settings_store.add_provider(payload)
    except settings_store.SettingsError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(provider), 201


@app.put("/api/settings/providers/<provider_id>")
def update_provider(provider_id):
    payload = request.get_json(silent=True) or {}
    try:
        provider = settings_store.update_provider(provider_id, payload)
    except settings_store.SettingsError as exc:
        status = 404 if str(exc) == "provider not found" else 400
        return jsonify({"error": str(exc)}), status
    return jsonify(provider)


@app.delete("/api/settings/providers/<provider_id>")
def delete_provider(provider_id):
    try:
        result = settings_store.delete_provider(provider_id)
    except settings_store.SettingsError as exc:
        status = 404 if str(exc) == "provider not found" else 400
        return jsonify({"error": str(exc)}), status
    return jsonify(result)


@app.post("/api/settings/providers/<provider_id>/test")
def test_provider(provider_id):
    try:
        provider = settings_store.get_provider(provider_id)
    except settings_store.SettingsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404

    try:
        return jsonify(provider_adapter.test_provider(provider))
    except provider_adapter.ProviderError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


@app.get("/content-studio")
def page_content_studio():
    return _coming_soon("content-studio")


@app.get("/ideas")
def page_ideas():
    return _coming_soon("ideas")


@app.get("/content-pipeline")
def page_content_pipeline():
    return _coming_soon("pipeline")


@app.get("/assets")
def page_assets():
    return _coming_soon("assets")


@app.get("/projects")
def page_projects():
    return _coming_soon("projects")


@app.get("/analytics")
def page_analytics():
    return _coming_soon("analytics")


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
    renders_root = os.path.realpath(str(DATA_ROOT / "renders"))
    assets_root = os.path.realpath(os.path.join(project_root, "static", "assets"))
    allowed_roots = [renders_root, assets_root]

    if not filename or ".." in filename or "\\" in filename:
        return jsonify({"error": "invalid path"}), 400
    if filename.startswith("/") or os.path.isabs(filename) or ":" in filename:
        return jsonify({"error": "invalid path"}), 400

    normalized = filename.replace("\\", "/")

    if normalized.startswith("data/renders/"):
        candidate = os.path.realpath(
            os.path.join(renders_root, normalized[len("data/renders/"):])
        )
    elif normalized.startswith("static/assets/"):
        candidate = os.path.realpath(
            os.path.join(assets_root, normalized[len("static/assets/"):])
        )
    else:
        # Legacy callers pass a path relative to static/assets.
        candidate = os.path.realpath(os.path.join(assets_root, normalized))

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
    payload = request.get_json(silent=True) or {}
    topic = str(payload.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "topic required"}), 400
    if len(topic) > MAX_TOPIC_LENGTH:
        return jsonify({
            "error": f"topic must be {MAX_TOPIC_LENGTH} characters or fewer"
        }), 400
    item = create_item(topic)
    return jsonify(item)


@app.post("/api/action/<int:item_id>")
def action(item_id):
    # One mutation at a time: the handler loads state, mutates it, and saves it.
    with locked():
        return _handle_action(item_id)


def _resolve_idea(item, selected):
    """Return the idea whose title matches ``selected``, or None.

    Exact match first, then a case-insensitive exact match. Substring matching
    was ambiguous when two ideas shared a phrase, so it is intentionally gone.
    """
    ideas = [idea for idea in (item.get("ideas") or []) if isinstance(idea, dict)]
    for idea in ideas:
        if idea.get("title") == selected:
            return idea
    lowered = selected.lower()
    for idea in ideas:
        if str(idea.get("title", "")).lower() == lowered:
            return idea
    return None


def _render_failed(result):
    """True when Kite reported a problem and produced no usable asset."""
    if not isinstance(result, dict) or not result.get("note"):
        return False
    assets = (
        result.get("slides") or result.get("frames")
        or result.get("scenes") or result.get("text_file")
    )
    return not assets


def _handle_action(item_id):
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

        idea = _resolve_idea(item, selected)
        if idea is None:
            return jsonify({"error": "selected idea is not in this item's ideas"}), 400

        selected_format = str(idea.get("format") or "CAROUSEL").upper()
        if selected_format not in SUPPORTED_FORMATS:
            selected_format = "CAROUSEL"

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

        if _render_failed(design_result):
            return jsonify({
                "error": "Kite could not render: " + str(design_result.get("note"))
            }), 400

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
        # state, so the snapshot is not a stale pre-publish copy. If the
        # configured publisher is not available, refuse before saving anything.
        item["published"] = True
        item["stage"] = "done"
        item["status"] = "published_local"

        try:
            result = orin(item)
        except PublishError as exc:
            return jsonify({"error": str(exc)}), 400

        add_activity(
            s,
            "Item " + str(item_id) + " saved as local publish package "
            "(publisher: " + str(result.get("mode")) + ")"
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
            if _render_failed(design_result):
                return jsonify({
                    "error": "Kite could not render: " + str(design_result.get("note"))
                }), 400
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
