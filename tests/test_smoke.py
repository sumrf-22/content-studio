"""Phase 0 smoke tests: the Flask app imports and serves the dashboard."""

from dashboard.app import app


def test_dashboard_loads():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Content Studio" in response.data


def test_state_endpoint_returns_expected_shape():
    client = app.test_client()
    response = client.get("/api/state")
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert isinstance(payload.get("items"), list)
    assert isinstance(payload.get("activity"), list)
