"""OpenAI-compatible adapter tests against a local HTTP server.

No real provider is contacted: a throwaway ``ThreadingHTTPServer`` on
127.0.0.1 answers each request according to a per-test plan, so retry, auth,
and timeout behaviour are exercised end to end through ``requests``.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

import core.llm as llm
import core.providers as providers
import core.settings as settings
from dashboard.app import app

RAW_KEY = "sk-test-local-provider-ab12"

SUCCESS_BODY = {
    "choices": [{"message": {"role": "assistant", "content": "OK"}}]
}


class _Handler(BaseHTTPRequestHandler):
    """Answers from ``server.plan``; records every request it receives."""

    server_version = "TestProvider/1.0"
    protocol_version = "HTTP/1.1"

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
        length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(length)
        try:
            body = json.loads(raw_body or b"{}")
        except ValueError:
            body = {}

        plan_list = self.server.plan
        index = len(self.server.requests)
        self.server.requests.append({
            "path": self.path,
            "headers": dict(self.headers),
            "body": body,
        })
        plan = plan_list[min(index, len(plan_list) - 1)]

        if plan.get("delay"):
            time.sleep(plan["delay"])

        payload = json.dumps(plan.get("body") or {}).encode("utf-8")
        try:
            self.send_response(plan.get("status", 200))
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            for name, value in (plan.get("headers") or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(payload)
        except OSError:
            # The client already gave up (timeout test).
            pass

    def log_message(self, *args):  # noqa: D401 - silence the test server
        return


@pytest.fixture()
def client():
    return app.test_client()


@pytest.fixture()
def provider_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.daemon_threads = True
    httpd.requests = []
    httpd.plan = [{"status": 200, "body": SUCCESS_BODY}]

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield SimpleNamespace(
            base_url=f"http://127.0.0.1:{httpd.server_address[1]}/v1",
            requests=httpd.requests,
            plan=lambda: list(httpd.plan),
            set_plan=lambda plan: setattr(httpd, "plan", list(plan)),
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(providers, "_sleep", lambda seconds: recorded.append(seconds))
    return recorded


def _add_provider(server, **overrides):
    payload = {
        "name": "Local provider",
        "base_url": server.base_url,
        "model": "local-model",
        "api_key": RAW_KEY,
    }
    payload.update(overrides)
    created = settings.add_provider(payload)
    return settings.get_provider(created["id"])


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_chat_posts_openai_compatible_request(provider_server):
    provider = _add_provider(provider_server)

    assert providers.chat(provider, [{"role": "user", "content": "hi"}]) == "OK"

    assert len(provider_server.requests) == 1
    request = provider_server.requests[0]
    assert request["path"] == "/v1/chat/completions"
    assert request["headers"]["Authorization"] == f"Bearer {RAW_KEY}"
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["body"] == {
        "model": "local-model",
        "messages": [{"role": "user", "content": "hi"}],
    }


def test_chat_strips_trailing_slash_from_base_url(provider_server):
    provider = _add_provider(provider_server, base_url=provider_server.base_url + "/")

    assert providers.chat(provider, [{"role": "user", "content": "hi"}]) == "OK"
    assert provider_server.requests[0]["path"] == "/v1/chat/completions"


def test_max_tokens_is_forwarded_when_requested(provider_server):
    provider = _add_provider(provider_server)

    providers.chat(
        provider, [{"role": "user", "content": "hi"}], max_tokens=16
    )

    assert provider_server.requests[0]["body"]["max_tokens"] == 16


# ---------------------------------------------------------------------------
# Auth and error handling
# ---------------------------------------------------------------------------


def test_401_is_a_clear_error_without_the_key(provider_server, sleeps):
    provider_server.set_plan([{"status": 401, "body": {"error": "bad key"}}])
    provider = _add_provider(provider_server)

    with pytest.raises(providers.ProviderError) as error:
        providers.chat(provider, [{"role": "user", "content": "hi"}])

    message = str(error.value)
    assert "HTTP 401" in message
    assert "rejected the API key" in message
    assert RAW_KEY not in message
    assert len(provider_server.requests) == 1
    assert sleeps == []  # auth errors are not retried


def test_429_is_retried_then_succeeds(provider_server, sleeps):
    provider_server.set_plan([
        {"status": 429, "body": {"error": "slow down"}},
        {"status": 200, "body": SUCCESS_BODY},
    ])
    provider = _add_provider(provider_server)

    assert providers.chat(provider, [{"role": "user", "content": "hi"}]) == "OK"

    assert len(provider_server.requests) == 2
    assert sleeps, "the retry must back off"
    assert all(seconds >= 0 for seconds in sleeps)


def test_persistent_429_reports_rate_limiting_after_the_attempt_limit(
    provider_server, sleeps
):
    provider_server.set_plan([{"status": 429, "body": {"error": "nope"}}])
    provider = _add_provider(provider_server)

    with pytest.raises(providers.ProviderError) as error:
        providers.chat(provider, [{"role": "user", "content": "hi"}], attempts=3)

    message = str(error.value)
    assert "rate limited" in message
    assert "3 attempts" in message
    assert len(provider_server.requests) == 3
    assert len(sleeps) == 2


def test_retry_after_header_is_honoured(provider_server, sleeps):
    provider_server.set_plan([
        {"status": 429, "headers": {"Retry-After": "0"}, "body": {}},
        {"status": 200, "body": SUCCESS_BODY},
    ])
    provider = _add_provider(provider_server)

    providers.chat(provider, [{"role": "user", "content": "hi"}])

    assert sleeps == [0.0]


def test_5xx_is_retried_and_then_reported(provider_server, sleeps):
    provider_server.set_plan([{"status": 503, "body": {}}])
    provider = _add_provider(provider_server)

    with pytest.raises(providers.ProviderError) as error:
        providers.chat(provider, [{"role": "user", "content": "hi"}], attempts=2)

    assert "HTTP 503" in str(error.value)
    assert len(provider_server.requests) == 2
    assert len(sleeps) == 1


def test_timeout_is_reported_without_retrying_forever(provider_server, sleeps):
    provider_server.set_plan([{"status": 200, "body": SUCCESS_BODY, "delay": 1.0}])
    provider = _add_provider(provider_server)

    started = time.monotonic()
    with pytest.raises(providers.ProviderError) as error:
        providers.chat(
            provider, [{"role": "user", "content": "hi"}], timeout=0.2
        )
    elapsed = time.monotonic() - started

    assert "timed out after 0.2s" in str(error.value)
    assert RAW_KEY not in str(error.value)
    assert elapsed < 0.9, elapsed
    assert sleeps == []


def test_unexpected_response_shape_is_reported(provider_server):
    provider_server.set_plan([{"status": 200, "body": {"choices": []}}])
    provider = _add_provider(provider_server)

    with pytest.raises(providers.ProviderError) as error:
        providers.chat(provider, [{"role": "user", "content": "hi"}])

    assert "unexpected response shape" in str(error.value)


# ---------------------------------------------------------------------------
# Test button and LLM wiring
# ---------------------------------------------------------------------------


def test_provider_test_endpoint_reports_success(client, provider_server):
    created = client.post("/api/settings/providers", json={
        "name": "Local provider",
        "base_url": provider_server.base_url,
        "model": "local-model",
        "api_key": RAW_KEY,
    })
    provider_id = created.get_json()["id"]

    response = client.post(f"/api/settings/providers/{provider_id}/test", json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["provider_id"] == provider_id
    assert payload["reply"] == "OK"
    assert RAW_KEY not in response.get_data(as_text=True)

    sent = provider_server.requests[0]
    assert sent["body"]["messages"][0]["content"]
    assert sent["headers"]["Authorization"] == f"Bearer {RAW_KEY}"


def test_provider_test_endpoint_reports_401(client, provider_server):
    provider_server.set_plan([{"status": 401, "body": {"error": "bad key"}}])
    created = client.post("/api/settings/providers", json={
        "name": "Local provider",
        "base_url": provider_server.base_url,
        "model": "local-model",
        "api_key": RAW_KEY,
    })
    provider_id = created.get_json()["id"]

    response = client.post(f"/api/settings/providers/{provider_id}/test", json={})

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["ok"] is False
    assert "HTTP 401" in payload["error"]
    assert RAW_KEY not in response.get_data(as_text=True)


def test_generate_uses_the_default_provider(provider_server):
    _add_provider(provider_server)
    settings.update_provider(
        settings.list_providers()[0]["id"], {"model": "local-model"}
    )

    assert llm.generate("a topic") == "OK"
    assert provider_server.requests[0]["path"] == "/v1/chat/completions"


def test_generate_raises_instead_of_falling_back_to_mock(provider_server):
    provider_server.set_plan([{"status": 401, "body": {}}])
    _add_provider(provider_server)

    with pytest.raises(llm.LLMError) as error:
        llm.generate("a topic")

    assert "HTTP 401" in str(error.value)


def test_generate_is_mock_when_no_provider_is_configured(provider_server):
    first = llm.generate("vastu tips for home")

    assert isinstance(first, str) and first
    assert provider_server.requests == []
    assert first == llm.generate("vastu tips for home")
