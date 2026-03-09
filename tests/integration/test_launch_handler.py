from __future__ import annotations

import time

from fastapi.testclient import TestClient

from nblaunch.app import create_app
from nblaunch.config import Settings
from nblaunch.security import sign_message


def _settings() -> Settings:
    return Settings(
        hmac_secret="secret",
        service_token="token",
        hub_api_url="https://hub.example/hub/api",
        notebook_base_dir="/srv/notebooks",
        signature_ttl_seconds=300,
    )


def _valid_query(nb: str = "gallery/notebook.ipynb", ts: int | None = None) -> dict[str, str]:
    ts_value = int(time.time()) if ts is None else ts
    return {
        "nb": nb,
        "ts": str(ts_value),
        "sig": sign_message("secret", nb, ts_value),
    }


def test_launch_with_valid_signature_reaches_placeholder_501() -> None:
    client = TestClient(create_app(_settings()))
    response = client.get("/launch", params=_valid_query())

    assert response.status_code == 501


def test_launch_missing_params_returns_400() -> None:
    client = TestClient(create_app(_settings()))
    response = client.get("/launch", params={"nb": "gallery/notebook.ipynb"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_params"


def test_launch_invalid_notebook_id_returns_400() -> None:
    client = TestClient(create_app(_settings()))
    params = _valid_query(nb="../escape.ipynb")
    response = client.get("/launch", params=params)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_notebook_id"


def test_launch_invalid_timestamp_returns_400() -> None:
    client = TestClient(create_app(_settings()))
    response = client.get(
        "/launch",
        params={
            "nb": "gallery/notebook.ipynb",
            "ts": "not-a-number",
            "sig": "a" * 64,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_timestamp"


def test_launch_expired_timestamp_returns_401() -> None:
    client = TestClient(create_app(_settings()))
    params = _valid_query(ts=int(time.time()) - 301)
    response = client.get("/launch", params=params)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_timestamp_window"


def test_launch_invalid_signature_returns_401() -> None:
    client = TestClient(create_app(_settings()))
    params = _valid_query()
    params["sig"] = "0" * 64
    response = client.get("/launch", params=params)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_signature"
