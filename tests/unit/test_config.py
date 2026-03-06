from __future__ import annotations

import pytest

from nblaunch.config import ConfigError, load_settings


def _base_env() -> dict[str, str]:
    return {
        "NBLAUNCH_HMAC_SECRET": "secret",
        "NBLAUNCH_SERVICE_TOKEN": "token",
        "NBLAUNCH_HUB_API_URL": "https://hub.example/hub/api",
        "NBLAUNCH_NOTEBOOK_BASE_DIR": "/srv/notebooks",
    }


def test_load_settings_parses_required_and_defaults() -> None:
    settings = load_settings(_base_env())

    assert settings.hmac_secret == "secret"
    assert settings.service_token == "token"
    assert settings.hub_api_url == "https://hub.example/hub/api"
    assert settings.notebook_base_dir == "/srv/notebooks"
    assert settings.signature_ttl_seconds == 300
    assert settings.max_notebook_bytes == 10 * 1024 * 1024


def test_load_settings_missing_required_raises() -> None:
    env = _base_env()
    del env["NBLAUNCH_HMAC_SECRET"]

    with pytest.raises(ConfigError, match="missing required setting"):
        load_settings(env)


def test_load_settings_invalid_integer_raises() -> None:
    env = _base_env()
    env["NBLAUNCH_SIGNATURE_TTL_SECONDS"] = "nope"

    with pytest.raises(ConfigError, match="invalid integer"):
        load_settings(env)


def test_load_settings_requires_absolute_notebook_path() -> None:
    env = _base_env()
    env["NBLAUNCH_NOTEBOOK_BASE_DIR"] = "relative/path"

    with pytest.raises(ConfigError, match="absolute path"):
        load_settings(env)


def test_load_settings_requires_absolute_hub_api_url() -> None:
    env = _base_env()
    env["NBLAUNCH_HUB_API_URL"] = "not-a-url"

    with pytest.raises(ConfigError, match="absolute http"):
        load_settings(env)
