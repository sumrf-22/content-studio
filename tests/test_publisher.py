"""Phase 6 tests: the mock publisher is the only supported target.

Real Meta Graph publishing stays disabled until the Instagram account and Meta
app are confirmed, so a misconfigured publisher must fail loudly and leave the
item unpublished instead of writing a misleading snapshot.
"""

import json

import pytest

from agents import orin
from core.state import load
from dashboard.app import app


@pytest.fixture()
def client(isolated_data):
    return app.test_client()


def _to_publish_stage(client, topic="Publisher topic"):
    item = client.post("/api/idea", json={"topic": topic}).get_json()
    item_id = item["id"]
    item = client.post(
        f"/api/action/{item_id}", json={"action": "approve_idea"}
    ).get_json()
    item = client.post(
        f"/api/action/{item_id}",
        json={"action": "select_idea", "selected_idea": item["ideas"][0]["title"]},
    ).get_json()
    item = client.post(
        f"/api/action/{item_id}", json={"action": "approve_copy"}
    ).get_json()
    item = client.post(
        f"/api/action/{item_id}", json={"action": "approve_design"}
    ).get_json()
    assert item["stage"] == "publish"
    return item


def test_mock_is_the_default_publisher(monkeypatch):
    monkeypatch.setattr(orin, "PUBLISHER", "mock")
    assert orin.describe()["mode"] == "mock"
    assert orin.describe()["target"] == "local"


def test_publish_writes_a_mock_package(client, isolated_data, monkeypatch):
    monkeypatch.setattr(orin, "PUBLISHER", "mock")
    item = _to_publish_stage(client)
    item_id = item["id"]

    response = client.post(f"/api/action/{item_id}", json={"action": "publish"})
    assert response.status_code == 200

    published = response.get_json()
    assert published["stage"] == "done"
    assert published["status"] == "published_local"
    assert published["publish"]["mode"] == "mock"
    assert published["publish"]["target"] == "local"

    snapshot_path = isolated_data / "published" / f"item_{item_id}.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["publish"]["mode"] == "mock"
    assert snapshot["stage"] == "done"

    state = load()
    assert state["items"][0]["publish"]["mode"] == "mock"
    assert "publisher: mock" in state["activity"][0]["message"]


@pytest.mark.parametrize("mode", ["instagram", "meta", "graph", "live"])
def test_non_mock_publishers_are_refused(client, isolated_data, monkeypatch, mode):
    monkeypatch.setattr(orin, "PUBLISHER", mode)
    item = _to_publish_stage(client, f"Refused {mode}")
    item_id = item["id"]

    response = client.post(f"/api/action/{item_id}", json={"action": "publish"})

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert mode in error
    assert "disabled" in error
    assert "Meta app" in error

    # Nothing was published: stage, flag and files are all unchanged.
    stored = load()["items"][0]
    assert stored["stage"] == "publish"
    assert stored["published"] is False
    assert "publish" not in stored
    assert not (isolated_data / "published" / f"item_{item_id}.json").exists()


def test_refusal_does_not_add_activity(client, monkeypatch):
    monkeypatch.setattr(orin, "PUBLISHER", "instagram")
    item = _to_publish_stage(client, "Refusal activity")
    before = len(load()["activity"])

    response = client.post(f"/api/action/{item['id']}", json={"action": "publish"})
    assert response.status_code == 400
    assert len(load()["activity"]) == before
