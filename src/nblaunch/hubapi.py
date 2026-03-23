"""Hub API client helpers for nblaunch home-subpath resolution."""

from __future__ import annotations

from json import JSONDecodeError, loads
from pathlib import Path
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .storage import StorageError, resolve_user_root_from_home_subpath


NBLAUNCH_HOME_SUBPATH_API_PATH = "/services/nblaunch/home-subpath"


class HubApiError(RuntimeError):
    """Raised when the Hub API lookup fails or returns invalid data."""


class HubApiAuthorizationError(HubApiError):
    """Raised when the Hub API rejects the nblaunch service identity."""


class HomeSubpathNotFoundError(HubApiError):
    """Raised when the Hub API does not provide a user home-subpath mapping."""


class HubApiFetcher(Protocol):
    def __call__(self, *, url: str, token: str, timeout_seconds: int) -> object:
        ...


def _home_subpath_url(hub_api_url: str, username: str) -> str:
    return f"{hub_api_url.rstrip('/')}{NBLAUNCH_HOME_SUBPATH_API_PATH}/{quote(username, safe='')}"


def _default_fetch_json(*, url: str, token: str, timeout_seconds: int) -> object:
    request = Request(
        url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        if exc.code == 404:
            raise HomeSubpathNotFoundError("user home mapping was not found") from exc
        if exc.code in {401, 403}:
            raise HubApiAuthorizationError("Hub API rejected nblaunch service authorization") from exc
        raise HubApiError(f"Hub API request failed with status {exc.code}") from exc
    except URLError as exc:
        raise HubApiError("failed to reach Hub API") from exc

    try:
        return loads(payload)
    except JSONDecodeError as exc:
        raise HubApiError("Hub API returned invalid JSON") from exc


def resolve_user_root(
    *,
    hub_api_url: str,
    service_token: str,
    notebook_base_dir: str | Path,
    username: str,
    timeout_seconds: int,
    fetch_json: HubApiFetcher | None = None,
) -> Path:
    fetch = _default_fetch_json if fetch_json is None else fetch_json
    payload = fetch(
        url=_home_subpath_url(hub_api_url, username),
        token=service_token,
        timeout_seconds=timeout_seconds,
    )

    if not isinstance(payload, dict):
        raise HubApiError("Hub API response must be a JSON object")
    payload_dict = cast(dict[str, object], payload)

    payload_username = payload_dict.get("username")
    if payload_username != username:
        raise HubApiError("Hub API response username mismatch")

    home_subpath = payload_dict.get("home_subpath")
    if home_subpath is None or home_subpath == "":
        raise HomeSubpathNotFoundError("user home mapping was not found")
    if not isinstance(home_subpath, str):
        raise HubApiError("Hub API response home_subpath must be a string")

    try:
        return resolve_user_root_from_home_subpath(
            base_dir=Path(notebook_base_dir),
            home_subpath=home_subpath,
        )
    except StorageError as exc:
        raise HubApiError("Hub API returned an invalid home_subpath") from exc
