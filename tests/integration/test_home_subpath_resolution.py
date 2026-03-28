from __future__ import annotations

from pathlib import Path
import time

from fastapi import Request
from fastapi.testclient import TestClient

from nblaunch.app import create_app
from nblaunch.config import Settings
from nblaunch.hubapi import HubApiAuthorizationError, resolve_user_root
from nblaunch.nbgallery import NotebookPayload
from nblaunch.security import sign_message


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        hmac_secret="secret",
        service_token="token",
        hub_api_url="https://hub.example/hub/api",
        gallery_base_url="https://gallery.example/api",
        notebook_base_dir=str(tmp_path),
        signature_ttl_seconds=300,
        jupyterhub_base_url="/hub",
    )


class _AuthenticatedServiceAuth:
    _username: str

    def __init__(self, username: str) -> None:
        self._username = username

    def current_user(self, _request: Request) -> str | None:
        return self._username

    def login_redirect(self, _request: Request) -> object:
        raise AssertionError("login_redirect should not be called in authenticated tests")

    async def oauth_callback(self, _request: Request) -> object:
        raise AssertionError("oauth_callback should not be called in authenticated tests")


def _valid_query(nb: str = "gallery/notebook", ts: int | None = None) -> dict[str, str]:
    ts_value = int(time.time()) if ts is None else ts
    return {
        "nb": nb,
        "ts": str(ts_value),
        "sig": sign_message("secret", nb, ts_value),
    }


def test_launch_uses_hub_owned_home_subpath_mapping(tmp_path: Path) -> None:
    username = "User.Name+Demo"
    app = create_app(_settings(tmp_path))
    app.state.service_auth = _AuthenticatedServiceAuth(username)

    def _fake_fetch(**_: object) -> NotebookPayload:
        return NotebookPayload(
            notebook_id="gallery/notebook",
            content=b"{}",
            content_type="application/x-ipynb+json",
        )

    def _hub_fetch_json(*, url: str, token: str, timeout_seconds: int) -> object:
        _ = url
        _ = token
        _ = timeout_seconds
        return {
            "username": username,
            "home_subpath": "users/user-name-demo",
        }

    def _resolve_user_root(*, request: Request, username: str, settings: Settings) -> Path:
        _ = request
        return resolve_user_root(
            hub_api_url=settings.hub_api_url,
            service_token=settings.service_token,
            notebook_base_dir=settings.notebook_base_dir,
            username=username,
            timeout_seconds=settings.http_timeout_seconds,
            fetch_json=_hub_fetch_json,
        )

    app.state.fetch_notebook = _fake_fetch
    app.state.resolve_user_root = _resolve_user_root
    client = TestClient(app)

    response = client.get("/launch", params=_valid_query(), follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/hub/user-redirect/lab/tree/nbgallery/gallery/notebook.ipynb"
    expected_root = tmp_path / "users" / "user-name-demo"
    expected_file = expected_root / "nbgallery" / "gallery" / "notebook.ipynb"
    assert expected_file.read_bytes() == b"{}"


def test_launch_surfaces_hub_authorization_failures(tmp_path: Path) -> None:
    username = "alice"
    app = create_app(_settings(tmp_path))
    app.state.service_auth = _AuthenticatedServiceAuth(username)

    def _fake_fetch(**_: object) -> NotebookPayload:
        return NotebookPayload(
            notebook_id="gallery/notebook",
            content=b"{}",
            content_type="application/x-ipynb+json",
        )

    def _resolve_user_root(*, request: Request, username: str, settings: Settings) -> Path:
        _ = request
        _ = username
        _ = settings
        raise HubApiAuthorizationError("Hub API rejected nblaunch service authorization")

    app.state.fetch_notebook = _fake_fetch
    app.state.resolve_user_root = _resolve_user_root
    client = TestClient(app)

    response = client.get("/launch", params=_valid_query(), follow_redirects=False)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "hub_home_lookup_forbidden"


def test_launch_rejects_malformed_home_subpath_from_hub(tmp_path: Path) -> None:
    username = "alice"
    app = create_app(_settings(tmp_path))
    app.state.service_auth = _AuthenticatedServiceAuth(username)

    def _fake_fetch(**_: object) -> NotebookPayload:
        return NotebookPayload(
            notebook_id="gallery/notebook",
            content=b"{}",
            content_type="application/x-ipynb+json",
        )

    def _resolve_user_root(*, request: Request, username: str, settings: Settings) -> Path:
        _ = request

        def _invalid_fetch_json(*, url: str, token: str, timeout_seconds: int) -> object:
            _ = url
            _ = token
            _ = timeout_seconds
            return {
                "username": username,
                "home_subpath": "../escape",
            }

        return resolve_user_root(
            hub_api_url=settings.hub_api_url,
            service_token=settings.service_token,
            notebook_base_dir=settings.notebook_base_dir,
            username=username,
            timeout_seconds=settings.http_timeout_seconds,
            fetch_json=_invalid_fetch_json,
        )

    app.state.fetch_notebook = _fake_fetch
    app.state.resolve_user_root = _resolve_user_root
    client = TestClient(app)

    response = client.get("/launch", params=_valid_query(), follow_redirects=False)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "hub_home_lookup_failed"
