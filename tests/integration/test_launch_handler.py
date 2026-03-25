from __future__ import annotations
# pyright: reportMissingTypeStubs=false

import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from nblaunch.app import create_app
from nblaunch.config import Settings
from nblaunch.nbgallery import GalleryTooLargeError, GalleryUpstreamError, NotebookPayload
from nblaunch.security import sign_message
from nblaunch.storage import StorageError


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _resolver_for(path: Path):
    def _resolver(*, request: Request, username: str, settings: Settings) -> Path:
        _ = request
        _ = username
        _ = settings
        return path

    return _resolver


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
    def current_user(self, _request: object) -> str | None:
        return "test-user"

    def login_redirect(self, _request: object) -> object:
        raise AssertionError("login_redirect should not be called in authenticated tests")

    async def oauth_callback(self, _request: object) -> object:
        raise AssertionError("oauth_callback should not be called in authenticated tests")


def _install_authenticated_user(app: FastAPI) -> None:
    app.state.service_auth = _AuthenticatedServiceAuth()


def _valid_query(nb: str = "gallery/notebook", ts: int | None = None) -> dict[str, str]:
    ts_value = int(time.time()) if ts is None else ts
    return {
        "nb": nb,
        "ts": str(ts_value),
        "sig": sign_message("secret", nb, ts_value),
    }


def test_launch_happy_path_fetches_stores_and_redirects(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    _install_authenticated_user(app)
    sample_bytes = (FIXTURES / "sample_notebook.ipynb").read_bytes()

    def _fake_fetch(**_: object) -> NotebookPayload:
        return NotebookPayload(
            notebook_id="gallery/notebook",
            content=sample_bytes,
            content_type="application/x-ipynb+json",
        )

    app.state.fetch_notebook = _fake_fetch
    app.state.resolve_user_root = _resolver_for(tmp_path / "user-a")
    client = TestClient(app)

    response = client.get("/launch", params=_valid_query(), follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/hub/user-redirect/lab/tree/nbgallery/gallery/notebook.ipynb"
    destination = tmp_path / "user-a" / "nbgallery" / "gallery" / "notebook.ipynb"
    assert destination.read_bytes() == sample_bytes


def test_launch_missing_params_returns_400() -> None:
    app = create_app(_settings(Path("/tmp/not-used")))
    _install_authenticated_user(app)
    client = TestClient(app)
    response = client.get("/launch", params={"nb": "gallery/notebook"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_params"


def test_launch_invalid_notebook_id_returns_400() -> None:
    app = create_app(_settings(Path("/tmp/not-used")))
    _install_authenticated_user(app)
    client = TestClient(app)
    response = client.get("/launch", params=_valid_query(nb="../escape"))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_notebook_id"


def test_launch_invalid_timestamp_returns_400() -> None:
    app = create_app(_settings(Path("/tmp/not-used")))
    _install_authenticated_user(app)
    client = TestClient(app)
    response = client.get(
        "/launch",
        params={"nb": "gallery/notebook", "ts": "not-a-number", "sig": "a" * 64},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_timestamp"


def test_launch_expired_timestamp_returns_401() -> None:
    app = create_app(_settings(Path("/tmp/not-used")))
    _install_authenticated_user(app)
    client = TestClient(app)
    response = client.get("/launch", params=_valid_query(ts=int(time.time()) - 301))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_timestamp_window"


def test_launch_invalid_signature_returns_401() -> None:
    app = create_app(_settings(Path("/tmp/not-used")))
    _install_authenticated_user(app)
    client = TestClient(app)
    params = _valid_query()
    params["sig"] = "0" * 64
    response = client.get("/launch", params=params)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_signature"


def test_launch_oversized_payload_returns_413_and_does_not_write(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    _install_authenticated_user(app)
    write_calls = {"count": 0}

    def _fake_fetch(**_: object) -> NotebookPayload:
        raise GalleryTooLargeError("gallery payload exceeds max size")

    def _fake_write(**_: object) -> object:
        write_calls["count"] += 1
        return None

    app.state.fetch_notebook = _fake_fetch
    app.state.write_notebook = _fake_write
    app.state.resolve_user_root = _resolver_for(tmp_path / "user-b")
    client = TestClient(app)

    response = client.get("/launch", params=_valid_query())

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "notebook_too_large"
    assert write_calls["count"] == 0


def test_launch_fetch_failure_returns_502_and_does_not_write(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    _install_authenticated_user(app)
    write_calls = {"count": 0}

    def _fake_fetch(**_: object) -> NotebookPayload:
        raise GalleryUpstreamError("upstream unavailable")

    def _fake_write(**_: object) -> object:
        write_calls["count"] += 1
        return None

    app.state.fetch_notebook = _fake_fetch
    app.state.write_notebook = _fake_write
    app.state.resolve_user_root = _resolver_for(tmp_path / "user-c")
    client = TestClient(app)

    response = client.get("/launch", params=_valid_query())

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "gallery_fetch_failed"
    assert write_calls["count"] == 0


def test_launch_storage_failure_returns_500_and_no_redirect(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    _install_authenticated_user(app)

    def _fake_fetch(**_: object) -> NotebookPayload:
        return NotebookPayload(
            notebook_id="gallery/notebook",
            content=b"{}",
            content_type="application/x-ipynb+json",
        )

    def _fake_write(**_: object) -> object:
        raise StorageError("disk full")

    app.state.fetch_notebook = _fake_fetch
    app.state.write_notebook = _fake_write
    app.state.resolve_user_root = _resolver_for(tmp_path / "user-d")
    client = TestClient(app)

    response = client.get("/launch", params=_valid_query())

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "storage_write_failed"
    assert "location" not in response.headers
