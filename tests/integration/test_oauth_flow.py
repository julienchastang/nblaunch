from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import Request
from fastapi.testclient import TestClient

from nblaunch.app import create_app
from nblaunch.config import Settings
from nblaunch.nbgallery import NotebookPayload
from nblaunch.security import sign_message


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        hmac_secret="secret",
        service_token="token",
        hub_api_url="https://hub.example/hub/api",
        notebook_base_dir=str(tmp_path),
        signature_ttl_seconds=300,
        jupyterhub_base_url="/hub",
    )


def _valid_query() -> dict[str, str]:
    ts_value = int(time.time())
    notebook_id = "gallery/notebook"
    return {
        "nb": notebook_id,
        "ts": str(ts_value),
        "sig": sign_message("secret", notebook_id, ts_value),
    }


def test_launch_redirects_to_hub_oauth_when_unauthenticated(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    response = client.get("/launch", params=_valid_query(), follow_redirects=False)

    assert response.status_code == 302
    parsed = urlparse(response.headers["location"])
    params = parse_qs(parsed.query)
    assert parsed.path == "/hub/api/oauth2/authorize"
    assert params["client_id"] == ["service-nblaunch"]
    assert params["redirect_uri"] == ["/hub/services/nblaunch/oauth_callback"]
    assert params["response_type"] == ["code"]
    assert params["state"]


def test_oauth_callback_roundtrip_restores_original_launch_request(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))

    def _fake_fetch(**_: object) -> NotebookPayload:
        return NotebookPayload(
            notebook_id="gallery/notebook",
            content=b"{}",
            content_type="application/x-ipynb+json",
        )

    app.state.fetch_notebook = _fake_fetch

    def _resolve_user_root(*, request: Request, username: str, settings: Settings) -> Path:
        _ = request
        _ = username
        _ = settings
        return tmp_path / "user-a"

    app.state.resolve_user_root = _resolve_user_root

    client = TestClient(app)
    initial = client.get("/launch", params=_valid_query(), follow_redirects=False)
    state = parse_qs(urlparse(initial.headers["location"]).query)["state"][0]

    callback = client.get(f"/oauth_callback?code=oauth-code&state={state}", follow_redirects=False)

    assert callback.status_code == 302
    restored = urlparse(callback.headers["location"])
    restored_params = parse_qs(restored.query)
    assert restored.path == "/launch"
    assert restored_params["nb"] == ["gallery/notebook"]

    final = client.get(callback.headers["location"], follow_redirects=False)

    assert final.status_code == 302
    assert final.headers["location"] == "/hub/user-redirect/lab/tree/nbgallery/gallery/notebook.ipynb"


def test_oauth_callback_rejects_invalid_state(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    _ = client.get("/launch", params=_valid_query(), follow_redirects=False)

    response = client.get("/oauth_callback?code=oauth-code&state=wrong-state", follow_redirects=False)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "oauth_callback_failed"
