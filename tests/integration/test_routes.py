from __future__ import annotations

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


def test_launch_placeholder_returns_501() -> None:
    client = TestClient(create_app(_settings()))
    response = client.get("/launch")

    assert response.status_code == 501


def test_oauth_callback_placeholder_returns_501() -> None:
    client = TestClient(create_app(_settings()))
    response = client.get("/oauth_callback")

    assert response.status_code == 501
