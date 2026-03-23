from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import time

from fastapi import Request
from fastapi.testclient import TestClient

from nblaunch.app import create_app
from nblaunch.config import Settings
from nblaunch.hubapi import resolve_user_root
from nblaunch.nbgallery import NotebookPayload
from nblaunch.security import sign_message


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[4]
HUB_HOME_SUBPATH = _load_module(
    ROOT / "jupyterhub" / "base" / "extraConfig" / "21-home-subpath.py",
    "hub_home_subpath",
)
HUB_HOME_SUBPATH_API = _load_module(
    ROOT / "jupyterhub" / "base" / "extraConfig" / "22-nblaunch-home-subpath-api.py",
    "hub_home_subpath_api",
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        hmac_secret="secret",
        service_token="token",
        hub_api_url="https://hub.example/hub/api",
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


def test_pre_spawn_hook_sets_home_subpath_and_preserves_existing_hook() -> None:
    calls: list[str] = []

    async def _existing_hook(spawner: SimpleNamespace) -> None:
        calls.append("existing")
        spawner.extra_flag = "preserved"

    spawner = SimpleNamespace(
        user=SimpleNamespace(name="User.Name+Demo"),
        volume_mounts=[
            {"name": "home", "mountPath": "/home/jovyan"},
            {"name": "shared", "mountPath": "/srv/shared"},
        ],
    )

    hook = HUB_HOME_SUBPATH.make_nblaunch_pre_spawn_hook(_existing_hook)
    asyncio.run(hook(spawner))

    assert calls == ["existing"]
    assert spawner.extra_flag == "preserved"
    assert spawner.volume_mounts[0]["subPath"] == "users/user-name-demo"
    assert "subPath" not in spawner.volume_mounts[1]


def test_home_subpath_api_rejects_unauthorized_service() -> None:
    response = HUB_HOME_SUBPATH_API.build_home_subpath_response(
        requester_service_name="other-service",
        username="alice",
    )

    assert response.status_code == 403
    assert response.body["error"]["code"] == "forbidden"


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
        response = HUB_HOME_SUBPATH_API.build_home_subpath_response(
            requester_service_name="nblaunch",
            username=username,
        )
        return response.body

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
