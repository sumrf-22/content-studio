"""Regression tests for the Phase 1 critical fixes."""

from PIL import Image

import core.llm as llm
import core.providers as providers
import core.settings as settings_module
import dashboard.app as app_module
from dashboard.app import app


class _FakeResponse:
    status_code = 200
    headers = {}

    def json(self):
        return {"choices": [{"message": {"content": "real-mode-response"}}]}


def test_generate_uses_the_default_provider_at_call_time(
    isolated_data, monkeypatch
):
    """Importing must not call out; generate() calls the configured provider."""
    settings_module.add_provider({
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openrouter/free",
        "api_key": "sk-or-v1-test-key-ab12",
    })
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse()

    monkeypatch.setattr(providers.requests, "post", fake_post)

    assert llm.generate("hello") == "real-mode-response"
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer sk-or-v1-test-key-ab12"
    assert kwargs["json"]["messages"][0]["content"] == "hello"
    assert kwargs["json"]["model"] == "openrouter/free"


def _fake_state(stage, ideas=None):
    return {
        "items": [
            {
                "id": 1,
                "topic": "test topic",
                "stage": stage,
                "status": "pending_approval",
                "ideas": ideas or [],
                "copy": None,
                "format": None,
                "design": None,
                "published": False,
            }
        ],
        "activity": [],
    }


def test_stage_action_vocabulary_rejects_stale_ui_action(monkeypatch):
    state = _fake_state("copy")
    monkeypatch.setattr(app_module, "load", lambda: state)
    monkeypatch.setattr(app_module, "save", lambda s: None)

    client = app.test_client()
    response = client.post("/api/action/1", json={"action": "approve_idea_review"})
    assert response.status_code == 400
    assert "not allowed at stage" in response.get_json()["error"]


def test_select_idea_requires_a_selection(monkeypatch):
    state = _fake_state("idea_review", [{"title": "Idea A", "format": "REEL"}])
    monkeypatch.setattr(app_module, "load", lambda: state)
    monkeypatch.setattr(app_module, "save", lambda s: None)

    client = app.test_client()
    response = client.post("/api/action/1", json={"action": "select_idea"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "idea required"


def test_select_idea_moves_item_to_copy(monkeypatch):
    state = _fake_state("idea_review", [{"title": "Idea A", "format": "REEL"}])
    monkeypatch.setattr(app_module, "load", lambda: state)
    monkeypatch.setattr(app_module, "save", lambda s: None)
    monkeypatch.setattr(app_module, "vera", lambda topic, fmt: {"format": fmt})

    client = app.test_client()
    response = client.post(
        "/api/action/1",
        json={"action": "select_idea", "selected_idea": "Idea A"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["stage"] == "copy"
    assert payload["format"] == "REEL"
    assert payload["selected_idea"] == "Idea A"


def test_slide_panel_covers_the_text_area(tmp_path):
    from agents.kite import _render_slide

    slide = {
        "headline": "Panel geometry",
        "subheadline": "Sub",
        "body": "Body",
        "cta": "CTA",
        "visual": "",
    }
    output = tmp_path / "slide.png"
    _render_slide(slide, 0, output)

    image = Image.open(output).convert("RGB")
    assert image.size == (1080, 1350)

    # Inside the readability panel (x=1000) must be darker than the
    # uncovered background just outside it (x=1040).
    inside = sum(image.getpixel((1000, 500)))
    outside = sum(image.getpixel((1040, 500)))
    assert inside < outside - 10
