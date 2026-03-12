from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from nblaunch.app import create_app
from nblaunch.config import Settings


def _settings() -> Settings:
    return Settings(
        hmac_secret="secret",
        service_token="token",
        hub_api_url="https://hub.example/hub/api",
        notebook_base_dir="/srv/notebooks",
    )


def test_healthz_returns_ok_payload() -> None:
    client = TestClient(create_app(_settings()))
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_launch_requires_authentication() -> None:
    client = TestClient(create_app(_settings()))
    response = client.get("/launch", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    parsed = urlparse(location)
    params = parse_qs(parsed.query)

    assert parsed.path == "/api/oauth2/authorize"
    assert params["client_id"] == ["service-nblaunch"]
    assert params["redirect_uri"] == ["/services/nblaunch/oauth_callback"]
    assert params["response_type"] == ["code"]
    assert "state" in params


def test_oauth_callback_without_pending_state_returns_401() -> None:
    client = TestClient(create_app(_settings()))
    response = client.get("/oauth_callback?code=abc&state=missing")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "oauth_callback_failed"
