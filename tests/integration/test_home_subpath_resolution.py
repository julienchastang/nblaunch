from __future__ import annotations

from pathlib import Path
import time

from fastapi import Request
from fastapi.testclient import TestClient

from nblaunch.app import create_app
from nblaunch.config import Settings
from nblaunch.nbgallery import NotebookPayload
from nblaunch.security import sign_message
from nblaunch.storage import UserRootResolutionError, resolve_user_root


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


def test_launch_uses_local_username_for_user_root(tmp_path: Path) -> None:
    username = "User.Name+Demo"
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
        return resolve_user_root(
            notebook_base_dir=settings.notebook_base_dir,
            username=username,
        )

    app.state.fetch_notebook = _fake_fetch
    app.state.resolve_user_root = _resolve_user_root
    client = TestClient(app)

    response = client.get("/launch", params=_valid_query(), follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/hub/user-redirect/lab/tree/nbgallery/gallery/notebook.ipynb"
    expected_root = tmp_path / "User.Name+Demo"
    expected_file = expected_root / "nbgallery" / "gallery" / "notebook.ipynb"
    assert expected_file.read_bytes() == b"{}"


def test_launch_returns_500_when_username_cannot_map_to_local_storage(tmp_path: Path) -> None:
    username = "../escape"
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
        return resolve_user_root(
            notebook_base_dir=settings.notebook_base_dir,
            username=username,
        )

    app.state.fetch_notebook = _fake_fetch
    app.state.resolve_user_root = _resolve_user_root
    client = TestClient(app)

    response = client.get("/launch", params=_valid_query(), follow_redirects=False)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "user_root_resolution_failed"


def test_launch_surfaces_explicit_user_root_resolution_errors(tmp_path: Path) -> None:
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
        raise UserRootResolutionError("unable to resolve local user root")

    app.state.fetch_notebook = _fake_fetch
    app.state.resolve_user_root = _resolve_user_root
    client = TestClient(app)

    response = client.get("/launch", params=_valid_query(), follow_redirects=False)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "user_root_resolution_failed"
