"""Phase 5 API tests: the full approval pipeline through Flask.

The suite drives the same endpoints the browser uses (create -> generate ideas
-> select idea -> approve copy -> approve design -> publish) against a temporary
data directory, so it verifies the API contract without touching real content.
"""

import json

import pytest

import dashboard.app as app_module
from dashboard.app import app
from core.models import SUPPORTED_FORMATS
from core.state import load


@pytest.fixture()
def client(isolated_data):
    return app.test_client()


def _action(client, item_id, action, **extra):
    payload = {"action": action}
    payload.update(extra)
    return client.post(f"/api/action/{item_id}", json=payload)


def _create(client, topic="API pipeline topic"):
    response = client.post("/api/idea", json={"topic": topic})
    assert response.status_code == 200
    return response.get_json()


def _to_design(client, idea_index=0):
    """Drive a fresh item from creation to the design stage."""
    item = _create(client)
    item = _action(client, item["id"], "approve_idea").get_json()
    idea = item["ideas"][idea_index]
    response = _action(client, item["id"], "select_idea", selected_idea=idea["title"])
    assert response.status_code == 200
    item = _action(client, item["id"], "approve_copy").get_json()
    return item, idea


def test_full_pipeline_reaches_published_local(client, isolated_data):
    created = _create(client, "Full API pipeline")
    assert created["stage"] == "idea"
    assert created["status"] == "pending_approval"
    assert created["published"] is False

    item_id = created["id"]

    reviewed = _action(client, item_id, "approve_idea").get_json()
    assert reviewed["stage"] == "idea_review"
    assert [idea["format"] for idea in reviewed["ideas"]] == list(SUPPORTED_FORMATS)

    chosen = reviewed["ideas"][0]
    assert chosen["format"] == "CAROUSEL"
    copied = _action(
        client, item_id, "select_idea", selected_idea=chosen["title"]
    ).get_json()
    assert copied["stage"] == "copy"
    assert copied["format"] == "CAROUSEL"
    assert copied["copy"]["format"] == "CAROUSEL"
    assert copied["copy"]["slides"]

    designed = _action(client, item_id, "approve_copy").get_json()
    assert designed["stage"] == "design"
    assert designed["design"]["provider"] == "local-pillow"
    assert designed["design"]["count"] == len(copied["copy"]["slides"])

    files = [entry["file"] for entry in designed["design"]["slides"]]
    assert files
    for relative in files:
        assert (isolated_data.parent / relative).resolve().is_file()

        asset = client.get("/api/asset/" + relative)
        assert asset.status_code == 200
        assert asset.headers["Content-Type"] == "image/png"
        assert asset.data.startswith(b"\x89PNG\r\n\x1a\n")

    ready = _action(client, item_id, "approve_design").get_json()
    assert ready["stage"] == "publish"
    assert ready["status"] == "pending_approval"

    published = _action(client, item_id, "publish").get_json()
    assert published["stage"] == "done"
    assert published["status"] == "published_local"
    assert published["published"] is True

    snapshot = json.loads(
        (isolated_data / "published" / f"item_{item_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert snapshot["stage"] == "done"
    assert snapshot["status"] == "published_local"
    assert snapshot["published"] is True
    assert snapshot["design"]["slides"]

    state = client.get("/api/state").get_json()
    assert [entry["id"] for entry in state["items"]] == [item_id]
    assert state["items"][0]["stage"] == "done"
    assert state["activity"], "activity log should record every human gate"

    single = client.get(f"/api/item/{item_id}").get_json()
    assert single["status"] == "published_local"


@pytest.mark.parametrize("fmt_index", range(len(SUPPORTED_FORMATS)))
def test_every_format_can_be_selected_and_rendered(client, fmt_index):
    item, idea = _to_design(client, fmt_index)
    fmt = SUPPORTED_FORMATS[fmt_index]

    assert idea["format"] == fmt
    assert item["format"] == fmt
    assert item["copy"]["format"] == fmt
    assert item["stage"] == "design"
    assert item["design"]["count"] >= 0

    if fmt == "TEXT_POST":
        assert item["design"]["text_file"].endswith("text_post.txt")
        assert item["design"]["text_preview"]
    else:
        assert item["design"]["count"] >= 1


def test_publish_before_the_publish_stage_is_rejected(client):
    item = _create(client, "Too early to publish")
    response = _action(client, item["id"], "publish")

    assert response.status_code == 400
    assert "not allowed at stage" in response.get_json()["error"]
    assert load()["items"][0]["stage"] == "idea"


def test_action_on_a_missing_item_returns_404(client):
    response = _action(client, 4242, "approve_idea")
    assert response.status_code == 404
    assert response.get_json()["error"] == "not found"


def test_unknown_action_is_rejected(client):
    item = _create(client, "Unknown action")
    response = _action(client, item["id"], "delete_everything")

    assert response.status_code == 400
    assert "not allowed" in response.get_json()["error"]


def test_select_idea_is_only_allowed_after_ideas_exist(client):
    item = _create(client, "No ideas yet")
    response = _action(client, item["id"], "select_idea", selected_idea="Anything")

    assert response.status_code == 400
    assert "is not allowed at stage 'idea'" in response.get_json()["error"]


def test_select_idea_requires_a_title(client):
    item = _create(client, "Missing title")
    _action(client, item["id"], "approve_idea")

    response = _action(client, item["id"], "select_idea")
    assert response.status_code == 400
    assert response.get_json()["error"] == "idea required"


def test_render_failure_keeps_the_item_at_copy(client, monkeypatch):
    item = _create(client, "Broken renderer")
    item = _action(client, item["id"], "approve_idea").get_json()
    item = _action(
        client, item["id"], "select_idea", selected_idea=item["ideas"][0]["title"]
    ).get_json()

    monkeypatch.setattr(
        app_module,
        "kite",
        lambda item_id, copy, fmt: {"provider": "local-pillow", "count": 0,
                                    "slides": [], "note": "disk full"},
    )

    response = _action(client, item["id"], "approve_copy")
    assert response.status_code == 400
    assert "disk full" in response.get_json()["error"]

    stored = load()["items"][0]
    assert stored["stage"] == "copy"
    assert stored["design"] is None


def test_reject_regenerates_copy_without_advancing(client):
    item = _create(client, "Reject and regenerate")
    item = _action(client, item["id"], "approve_idea").get_json()
    item = _action(
        client, item["id"], "select_idea", selected_idea=item["ideas"][0]["title"]
    ).get_json()
    first_copy = item["copy"]

    response = _action(client, item["id"], "reject")
    assert response.status_code == 200

    refreshed = response.get_json()
    assert refreshed["stage"] == "copy"
    assert refreshed["copy"]["format"] == first_copy["format"]
    assert refreshed["copy"]["slides"]


def test_published_item_rejects_further_actions(client):
    item, _ = _to_design(client)
    _action(client, item["id"], "approve_design")
    _action(client, item["id"], "publish")

    response = _action(client, item["id"], "reject")
    assert response.status_code == 400
    assert load()["items"][0]["stage"] == "done"


def test_asset_route_serves_text_assets(client, isolated_data):
    item = _create(client, "Text asset")
    item = _action(client, item["id"], "approve_idea").get_json()
    text_index = SUPPORTED_FORMATS.index("TEXT_POST")
    item = _action(
        client, item["id"], "select_idea", selected_idea=item["ideas"][text_index]["title"]
    ).get_json()

    response = _action(client, item["id"], "approve_copy")
    assert response.status_code == 200

    design = response.get_json()["design"]
    asset = client.get("/api/asset/" + design["text_file"])
    assert asset.status_code == 200
    assert asset.headers["Content-Type"].startswith("text/plain")
    assert b"HOOK" in asset.data or b"POST_TEXT" in asset.data
