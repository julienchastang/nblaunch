from __future__ import annotations

from pathlib import Path

import pytest

from nblaunch.hubapi import HomeSubpathNotFoundError, HubApiError, resolve_user_root


def _matching_fetcher(*, url: str, token: str, timeout_seconds: int) -> object:
    _ = url
    _ = token
    _ = timeout_seconds
    return {
        "username": "User.Name",
        "home_subpath": "users/user-name",
    }


def _mismatch_fetcher(*, url: str, token: str, timeout_seconds: int) -> object:
    _ = url
    _ = token
    _ = timeout_seconds
    return {
        "username": "bob",
        "home_subpath": "users/bob",
    }


def _invalid_subpath_fetcher(*, url: str, token: str, timeout_seconds: int) -> object:
    _ = url
    _ = token
    _ = timeout_seconds
    return {
        "username": "alice",
        "home_subpath": "../escape",
    }


def _missing_mapping_fetcher(*, url: str, token: str, timeout_seconds: int) -> object:
    _ = url
    _ = token
    _ = timeout_seconds
    return {
        "username": "alice",
        "home_subpath": "",
    }


def test_resolve_user_root_uses_hub_mapping_under_base_dir(tmp_path: Path) -> None:
    resolved = resolve_user_root(
        hub_api_url="https://hub.example/hub/api",
        service_token="token",
        notebook_base_dir=tmp_path,
        username="User.Name",
        timeout_seconds=10,
        fetch_json=_matching_fetcher,
    )

    assert resolved == tmp_path / "users" / "user-name"


def test_resolve_user_root_rejects_username_mismatch(tmp_path: Path) -> None:
    with pytest.raises(HubApiError, match="username mismatch"):
        _ = resolve_user_root(
            hub_api_url="https://hub.example/hub/api",
            service_token="token",
            notebook_base_dir=tmp_path,
            username="alice",
            timeout_seconds=10,
            fetch_json=_mismatch_fetcher,
        )


def test_resolve_user_root_rejects_invalid_home_subpath(tmp_path: Path) -> None:
    with pytest.raises(HubApiError, match="invalid home_subpath"):
        _ = resolve_user_root(
            hub_api_url="https://hub.example/hub/api",
            service_token="token",
            notebook_base_dir=tmp_path,
            username="alice",
            timeout_seconds=10,
            fetch_json=_invalid_subpath_fetcher,
        )


def test_resolve_user_root_raises_when_home_mapping_missing(tmp_path: Path) -> None:
    with pytest.raises(HomeSubpathNotFoundError, match="not found"):
        _ = resolve_user_root(
            hub_api_url="https://hub.example/hub/api",
            service_token="token",
            notebook_base_dir=tmp_path,
            username="alice",
            timeout_seconds=10,
            fetch_json=_missing_mapping_fetcher,
        )
