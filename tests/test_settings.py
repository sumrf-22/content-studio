"""BYOK provider settings: encrypted storage, validation, and CSRF.

Every test runs against a throwaway settings directory (autouse fixture in
``tests/conftest.py``) and a test-only Fernet key, so the real project
``.env`` and ``data/settings/`` are never touched.
"""

import json
import os

import pytest
from cryptography.fernet import Fernet

import core.llm as llm
import core.settings as settings
from dashboard.app import app

RAW_KEY = "sk-or-v1-0123456789abcdefab12"

OPENROUTER = {
    "name": "OpenRouter",
    "base_url": "https://openrouter.ai/api/v1",
    "model": "openrouter/free",
    "api_key": RAW_KEY,
}


@pytest.fixture()
def client():
    return app.test_client()


@pytest.fixture()
def provider_dir(isolate_provider_settings):
    """The isolated ``data/settings`` directory for this test."""
    return isolate_provider_settings


def _store_file(provider_dir):
    return provider_dir / "providers.json"


def _raw_store(provider_dir):
    return json.loads(_store_file(provider_dir).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------


def test_api_key_round_trips_through_fernet(provider_dir):
    created = settings.add_provider(dict(OPENROUTER))

    stored = _raw_store(provider_dir)["providers"][0]
    token = stored["api_key"]

    # A Fernet token, not the key.
    assert token != RAW_KEY
    assert token.startswith("gAAAAA")
    assert Fernet(os.environ[settings.SECRET_ENV]).decrypt(
        token.encode("ascii")
    ).decode("utf-8") == RAW_KEY
    assert settings.decrypt_key(token) == RAW_KEY

    # The public shape carries the mask, not the secret.
    assert created["api_key"] == "sk-or-...ab12"
    assert created["has_key"] is True


def test_raw_key_is_absent_from_disk_and_api(client, provider_dir):
    created = settings.add_provider(dict(OPENROUTER))

    on_disk = _store_file(provider_dir).read_text(encoding="utf-8")
    assert RAW_KEY not in on_disk
    assert "0123456789abcdef" not in on_disk
    assert _raw_store(provider_dir)["providers"][0]["api_key_last4"] == "ab12"

    response = client.get("/api/settings/providers")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert RAW_KEY not in body
    assert "0123456789abcdef" not in body

    payload = response.get_json()
    assert payload["providers"][0]["id"] == created["id"]
    assert payload["providers"][0]["api_key"] == "sk-or-...ab12"
    assert payload["mode"]["mode"] == "live"


def test_mask_uses_the_provider_prefix_and_last_four():
    assert settings.masked_key({
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_last4": "ab12",
    }) == "sk-or-...ab12"
    assert settings.masked_key({
        "base_url": "https://token.sensenova.cn/v1",
        "api_key_last4": "wxyz",
    }) == "sk-...wxyz"
    assert settings.masked_key({
        "base_url": "https://gateway.example/v1",
        "api_key_last4": "9876",
    }) == "...9876"
    assert settings.masked_key({}) == ""


def test_empty_key_on_update_keeps_the_ciphertext(provider_dir):
    created = settings.add_provider(dict(OPENROUTER))
    before = _raw_store(provider_dir)["providers"][0]["api_key"]

    updated = settings.update_provider(created["id"], {
        "name": "OpenRouter renamed",
        "model": "openrouter/auto",
        "api_key": "",
    })

    stored = _raw_store(provider_dir)["providers"][0]
    assert stored["api_key"] == before
    assert stored["api_key_last4"] == "ab12"
    assert stored["model"] == "openrouter/auto"
    assert updated["name"] == "OpenRouter renamed"
    assert updated["api_key"] == "sk-or-...ab12"


def test_new_key_on_update_rotates_the_ciphertext(provider_dir):
    created = settings.add_provider(dict(OPENROUTER))
    before = _raw_store(provider_dir)["providers"][0]["api_key"]

    settings.update_provider(created["id"], {"api_key": "sk-or-v1-replacement-9999"})

    stored = _raw_store(provider_dir)["providers"][0]
    assert stored["api_key"] != before
    assert stored["api_key_last4"] == "9999"
    assert settings.decrypt_key(stored["api_key"]) == "sk-or-v1-replacement-9999"


def test_missing_secret_key_generates_one_and_writes_env(
    monkeypatch, tmp_path, provider_dir
):
    env_file = tmp_path / "provider.env"
    monkeypatch.setattr(settings, "ENV_FILE", env_file)
    monkeypatch.delenv(settings.SECRET_ENV, raising=False)

    created = settings.add_provider(dict(OPENROUTER))

    assert env_file.exists()
    contents = env_file.read_text(encoding="utf-8")
    assert f"{settings.SECRET_ENV}=" in contents
    generated = os.environ[settings.SECRET_ENV]
    assert Fernet(generated.encode("ascii"))
    assert contents.count(settings.SECRET_ENV) == 1

    # The provider saved in that same call is readable with the new key.
    stored = _raw_store(provider_dir)["providers"][0]
    assert settings.decrypt_key(stored["api_key"]) == RAW_KEY
    assert created["api_key"] == "sk-or-...ab12"


def test_missing_secret_key_never_rotates_on_decrypt(monkeypatch, tmp_path):
    env_file = tmp_path / "provider.env"
    monkeypatch.setattr(settings, "ENV_FILE", env_file)
    monkeypatch.delenv(settings.SECRET_ENV, raising=False)

    token = Fernet(Fernet.generate_key()).encrypt(b"some-key").decode("ascii")

    with pytest.raises(settings.SettingsError) as error:
        settings.decrypt_key(token)

    assert settings.SECRET_ENV in str(error.value)
    assert not env_file.exists(), "decrypt must not mint a new key"


def test_invalid_secret_key_is_reported(monkeypatch):
    monkeypatch.setenv(settings.SECRET_ENV, "not-a-fernet-key")

    with pytest.raises(settings.SettingsError) as error:
        settings.add_provider(dict(OPENROUTER))

    assert "not a valid Fernet key" in str(error.value)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "base_url",
    [
        "http://example.com/v1",
        "ftp://example.com/v1",
        "https://user:pass@example.com/v1",
        "https://example.com/v1?token=x",
        "https://example.com/v1#fragment",
        "example.com/v1",
        "/relative/path",
    ],
)
def test_insecure_or_malformed_base_url_is_rejected(base_url):
    payload = dict(OPENROUTER, base_url=base_url)

    with pytest.raises(settings.SettingsError):
        settings.add_provider(payload)


@pytest.mark.parametrize(
    "base_url",
    [
        "https://gateway.example.com/v1",
        "http://localhost:1234/v1",
        "http://127.0.0.1:1234/v1",
    ],
)
def test_https_and_localhost_base_urls_are_accepted(base_url):
    created = settings.add_provider(
        dict(OPENROUTER, name="Custom " + base_url, base_url=base_url)
    )

    assert created["base_url"] == base_url.rstrip("/")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "x", "base_url": "https://x.example/v1", "model": "m"},
        {"name": "", "base_url": "https://x.example/v1", "model": "m", "api_key": "k"},
        {"base_url": "https://x.example/v1", "model": "m", "api_key": "k"},
        {"name": "x", "model": "m", "api_key": "k"},
        {"name": "x", "base_url": "https://x.example/v1", "api_key": "k"},
        {"name": "x", "base_url": "https://x.example/v1", "model": "m"},
    ],
)
def test_required_fields_are_enforced(payload):
    with pytest.raises(settings.SettingsError):
        settings.add_provider(payload)


def test_duplicate_names_are_rejected():
    settings.add_provider(dict(OPENROUTER))

    with pytest.raises(settings.SettingsError) as error:
        settings.add_provider(dict(OPENROUTER, api_key="sk-or-v1-other-1111"))

    assert "already exists" in str(error.value)


# ---------------------------------------------------------------------------
# Default provider and mode
# ---------------------------------------------------------------------------


def test_mode_is_mock_without_a_provider():
    assert settings.mode_info()["mode"] == "mock"
    assert settings.default_provider() is None


def test_first_provider_becomes_default_and_mode_is_live():
    created = settings.add_provider(dict(OPENROUTER))

    assert created["is_default"] is True
    mode = settings.mode_info()
    assert mode["mode"] == "live"
    assert mode["provider_id"] == created["id"]
    assert mode["model"] == "openrouter/free"


def test_disabled_default_falls_back_to_mock():
    created = settings.add_provider(dict(OPENROUTER))
    settings.update_provider(created["id"], {"enabled": False})

    assert settings.mode_info()["mode"] == "mock"


def test_explicit_default_wins_and_delete_promotes_a_replacement():
    first = settings.add_provider(dict(OPENROUTER))
    second = settings.add_provider({
        "name": "Custom",
        "base_url": "https://gateway.example.com/v1",
        "model": "custom-model",
        "api_key": "custom-secret-key-9876",
    })
    assert second["is_default"] is False

    settings.update_provider(second["id"], {"is_default": True})
    assert settings.mode_info()["provider_id"] == second["id"]

    settings.delete_provider(second["id"])
    remaining = settings.list_providers()
    assert [provider["id"] for provider in remaining] == [first["id"]]
    assert remaining[0]["is_default"] is True
    assert settings.mode_info()["mode"] == "live"


# ---------------------------------------------------------------------------
# HTTP routes and CSRF
# ---------------------------------------------------------------------------


def test_provider_crud_through_the_api(client, provider_dir):
    created = client.post("/api/settings/providers", json=dict(OPENROUTER))
    assert created.status_code == 201
    provider = created.get_json()
    assert provider["api_key"] == "sk-or-...ab12"

    listed = client.get("/api/settings/providers").get_json()
    assert len(listed["providers"]) == 1
    assert listed["mode"]["mode"] == "live"

    updated = client.put(
        f"/api/settings/providers/{provider['id']}",
        json={"model": "openrouter/auto", "api_key": ""},
    )
    assert updated.status_code == 200
    assert updated.get_json()["model"] == "openrouter/auto"
    assert updated.get_json()["api_key"] == "sk-or-...ab12"

    deleted = client.delete(f"/api/settings/providers/{provider['id']}")
    assert deleted.status_code == 200
    assert client.get("/api/settings/providers").get_json()["providers"] == []


def test_invalid_payload_returns_400_without_saving(client, provider_dir):
    response = client.post(
        "/api/settings/providers", json=dict(OPENROUTER, base_url="http://example.com")
    )

    assert response.status_code == 400
    assert "https://" in response.get_json()["error"]
    assert not _store_file(provider_dir).exists()


def test_unknown_provider_returns_404(client):
    assert client.put("/api/settings/providers/nope", json={"name": "x"}).status_code == 404
    assert client.delete("/api/settings/providers/nope").status_code == 404
    assert client.post("/api/settings/providers/nope/test", json={}).status_code == 404


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/settings/providers"),
        ("put", "/api/settings/providers/abc123"),
        ("delete", "/api/settings/providers/abc123"),
        ("post", "/api/settings/providers/abc123/test"),
    ],
)
def test_mutations_reject_non_json_bodies(client, provider_dir, method, path):
    response = getattr(client, method)(
        path, data="name=x&api_key=leak", content_type="text/plain"
    )

    assert response.status_code == 415
    assert not _store_file(provider_dir).exists()


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/settings/providers"),
        ("put", "/api/settings/providers/abc123"),
        ("delete", "/api/settings/providers/abc123"),
        ("post", "/api/settings/providers/abc123/test"),
    ],
)
def test_mutations_reject_cross_origin_and_cross_site(
    client, provider_dir, method, path
):
    cross_origin = getattr(client, method)(
        path,
        json=dict(OPENROUTER),
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert cross_origin.status_code == 403
    assert "blocked" in cross_origin.get_json()["error"]

    cross_site = getattr(client, method)(
        path, json=dict(OPENROUTER), headers={"Sec-Fetch-Site": "cross-site"}
    )
    assert cross_site.status_code == 403

    assert not _store_file(provider_dir).exists()


def test_same_origin_json_mutation_is_allowed(client):
    response = client.post(
        "/api/settings/providers",
        json=dict(OPENROUTER),
        headers={"Origin": "http://localhost", "Sec-Fetch-Site": "same-origin"},
    )

    assert response.status_code == 201


def test_settings_page_shows_mock_mode_then_live(client):
    page = client.get("/settings").get_data(as_text=True)
    assert "Mock mode" in page
    assert "No enabled provider with an API key is set as the default." in page

    settings.add_provider(dict(OPENROUTER))
    page = client.get("/settings").get_data(as_text=True)
    assert "Live — OpenRouter" in page
    assert "openrouter/free" in page


def test_corrupt_provider_file_is_reported_not_ignored(client, provider_dir):
    provider_dir.mkdir(parents=True, exist_ok=True)
    _store_file(provider_dir).write_text("{not json", encoding="utf-8")

    page = client.get("/settings")
    assert page.status_code == 200
    assert "Configuration error" in page.get_data(as_text=True)

    listed = client.get("/api/settings/providers")
    assert listed.status_code == 500
    assert "unreadable" in listed.get_json()["error"]

    created = client.post("/api/settings/providers", json=dict(OPENROUTER))
    assert created.status_code == 400
    assert "unreadable" in created.get_json()["error"]


def test_provider_failure_is_a_clear_502_and_the_item_is_untouched(
    client, monkeypatch
):
    """A configured provider that fails must not silently fall back to mock."""
    settings.add_provider(dict(OPENROUTER))

    def boom(*args, **kwargs):
        raise llm.LLMError("Provider 'OpenRouter' rejected the API key (HTTP 401).")

    monkeypatch.setattr(llm, "generate", boom)

    created = client.post("/api/idea", json={"topic": "Provider failure topic"}).get_json()
    response = client.post(
        f"/api/action/{created['id']}", json={"action": "approve_idea"}
    )

    assert response.status_code == 502
    assert "HTTP 401" in response.get_json()["error"]

    stored = client.get(f"/api/item/{created['id']}").get_json()
    assert stored["stage"] == "idea"
    assert not stored.get("ideas")
