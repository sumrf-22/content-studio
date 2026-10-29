"""Phase 3 regression tests: state ids, serialized writes, request validation.

Every test that touches storage redirects `core.state` at a temporary folder so
the real `data/state.json` is never modified.
"""

import json
import threading

import pytest

import core.state as state_module
import dashboard.app as app_module
from dashboard.app import app


@pytest.fixture()
def temp_state(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(state_module, "DATA", data)
    monkeypatch.setattr(state_module, "STATE", data / "state.json")
    return data


@pytest.fixture()
def client():
    return app.test_client()


def test_create_item_ids_never_collide(temp_state):
    first = state_module.create_item("first")
    second = state_module.create_item("second")
    assert (first["id"], second["id"]) == (1, 2)

    loaded = state_module.load()
    loaded["items"] = [item for item in loaded["items"] if item["id"] != 1]
    state_module.save(loaded)

    third = state_module.create_item("third")
    assert third["id"] == 3
    assert [item["id"] for item in state_module.load()["items"]] == [3, 2]


def test_concurrent_creates_share_the_state_file(temp_state):
    errors = []
    results = []

    def worker(index):
        try:
            results.append(state_module.create_item(f"topic {index}")["id"])
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert sorted(results) == list(range(1, 9))
    saved = json.loads((temp_state / "state.json").read_text(encoding="utf-8"))
    assert sorted(item["id"] for item in saved["items"]) == list(range(1, 9))


def test_idea_endpoint_rejects_missing_body(client):
    response = client.post("/api/idea")
    assert response.status_code == 400
    assert response.get_json()["error"] == "topic required"


def test_idea_endpoint_rejects_overlong_topic(client):
    response = client.post("/api/idea", json={"topic": "x" * 301})
    assert response.status_code == 400
    assert "300 characters" in response.get_json()["error"]


def _fake_idea_state(ideas):
    return {
        "items": [
            {
                "id": 1,
                "topic": "test topic",
                "stage": "idea_review",
                "status": "pending_approval",
                "ideas": ideas,
                "copy": None,
                "format": None,
                "design": None,
                "published": False,
            }
        ],
        "activity": [],
    }


def test_select_idea_rejects_title_outside_the_item(client, monkeypatch):
    state = _fake_idea_state([{"title": "Idea A", "format": "REEL"}])
    monkeypatch.setattr(app_module, "load", lambda: state)
    monkeypatch.setattr(app_module, "save", lambda s: None)

    response = client.post(
        "/api/action/1",
        json={"action": "select_idea", "selected_idea": "Invented idea"},
    )
    assert response.status_code == 400
    assert "not in this item" in response.get_json()["error"]


def test_select_idea_uses_exact_title_not_substring(client, monkeypatch):
    ideas = [
        {"title": "Idea A", "format": "REEL"},
        {"title": "Idea AB", "format": "MEME"},
    ]
    state = _fake_idea_state(ideas)
    monkeypatch.setattr(app_module, "load", lambda: state)
    monkeypatch.setattr(app_module, "save", lambda s: None)
    monkeypatch.setattr(app_module, "vera", lambda topic, fmt: {"format": fmt})

    response = client.post(
        "/api/action/1",
        json={"action": "select_idea", "selected_idea": "Idea A"},
    )
    assert response.status_code == 200
    assert response.get_json()["format"] == "REEL"

    # A prefix that matches both ideas must not be guessed.
    state["items"][0]["stage"] = "idea_review"
    response = client.post(
        "/api/action/1",
        json={"action": "select_idea", "selected_idea": "Idea"},
    )
    assert response.status_code == 400


def test_unknown_idea_format_falls_back_to_carousel(client, monkeypatch):
    state = _fake_idea_state([{"title": "Weird", "format": "NOT_A_FORMAT"}])
    monkeypatch.setattr(app_module, "load", lambda: state)
    monkeypatch.setattr(app_module, "save", lambda s: None)
    monkeypatch.setattr(app_module, "vera", lambda topic, fmt: {"format": fmt})

    response = client.post(
        "/api/action/1",
        json={"action": "select_idea", "selected_idea": "Weird"},
    )
    assert response.status_code == 200
    assert response.get_json()["format"] == "CAROUSEL"
