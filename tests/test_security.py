"""Phase 4 security tests: parsing limits, CSRF guard, token auth, headers."""

import pytest

import dashboard.app as app_module
from dashboard.app import app


@pytest.fixture()
def client():
    return app.test_client()


@pytest.fixture()
def project_root(tmp_path, monkeypatch):
    """Redirect the asset route at a throwaway project tree."""
    root = tmp_path / "project"
    renders = root / "data" / "renders"
    renders.mkdir(parents=True)
    (renders / "ok.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    (root / "state.json").write_text("{}", encoding="utf-8")
    (root / "secret.txt").write_text("do not serve", encoding="utf-8")
    monkeypatch.setattr(app_module, "BASE_DIR", str(root))
    monkeypatch.setattr(app_module, "DATA_ROOT", root / "data")
    return root


@pytest.fixture()
def token(monkeypatch):
    monkeypatch.setitem(app.config, "ACCESS_TOKEN", "s3cret-token")
    return "s3cret-token"


def test_asset_route_serves_allowlisted_render(client, project_root):
    response = client.get("/api/asset/data/renders/ok.png")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/png"


@pytest.mark.parametrize(
    "path",
    [
        "/api/asset/../state.json",
        "/api/asset/data/renders/../../state.json",
        "/api/asset/static/assets/../../secret.txt",
        "/api/asset/C:/Windows/win.ini",
        "/api/asset/%2e%2e/state.json",
        "/api/asset/..%2Fstate.json",
    ],
)
def test_asset_route_blocks_traversal(client, project_root, path):
    response = client.get(path)
    assert response.status_code in {400, 403, 404}
    if response.status_code == 200:
        pytest.fail("traversal returned file content")
    assert b"do not serve" not in response.data


def test_asset_route_does_not_serve_state_file(client, project_root):
    response = client.get("/api/asset/state.json")
    assert response.status_code in {403, 404}
    assert b"items" not in response.data


def test_security_headers_are_present(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


def test_form_post_is_rejected(client):
    response = client.post(
        "/api/idea",
        data="topic=form",
        content_type="application/x-www-form-urlencoded",
    )
    assert response.status_code == 415
    assert "application/json" in response.get_json()["error"]


def test_cross_origin_json_post_is_rejected(client):
    response = client.post(
        "/api/idea",
        json={"topic": "evil"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403


def test_cross_site_fetch_metadata_is_rejected(client):
    response = client.post(
        "/api/idea",
        json={"topic": "evil"},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403


def test_same_origin_json_post_passes_the_guard(client, monkeypatch):
    monkeypatch.setattr(app_module, "create_item", lambda topic: {"id": 1, "topic": topic})
    response = client.post(
        "/api/idea",
        json={"topic": "ok"},
        headers={"Origin": "http://localhost", "Sec-Fetch-Site": "same-origin"},
    )
    assert response.status_code == 200


def test_token_is_required_when_configured(client, token):
    assert client.get("/api/state").status_code == 401
    assert client.get("/").status_code == 401

    allowed = client.get(
        "/api/state", headers={"X-Content-Studio-Token": token}
    )
    assert allowed.status_code == 200


def test_wrong_token_is_rejected(client, token):
    response = client.get(
        "/api/state", headers={"X-Content-Studio-Token": "wrong"}
    )
    assert response.status_code == 401


def test_token_query_sets_cookie(client, token):
    response = client.get("/?token=" + token)
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    cookie = response.headers.get("Set-Cookie", "")
    assert "cs_token=" in cookie
    assert "HttpOnly" in cookie

    # The cookie now authorizes the page and the API.
    assert client.get("/").status_code == 200
    assert client.get("/api/state").status_code == 200
