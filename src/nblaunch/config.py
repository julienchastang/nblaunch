"""Configuration loader for nblaunch."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ as os_environ
from os.path import isabs
from typing import Mapping
from urllib.parse import urlparse


class ConfigError(ValueError):
    """Raised when service configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    hmac_secret: str
    service_token: str
    hub_api_url: str
    notebook_base_dir: str
    signature_ttl_seconds: int = 300
    max_notebook_bytes: int = 10 * 1024 * 1024
    gallery_timeout_seconds: int = 10
    http_timeout_seconds: int = 10
    log_level: str = "INFO"
    jupyterhub_base_url: str = "/"


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"missing required setting: {name}")
    return value


def _int_setting(env: Mapping[str, str], name: str, default: int, min_value: int = 1) -> int:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"invalid integer for {name}: {raw}") from exc
    if value < min_value:
        raise ConfigError(f"{name} must be >= {min_value}")
    return value


def _validate_hub_api_url(hub_api_url: str) -> None:
    parsed = urlparse(hub_api_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError("NBLAUNCH_HUB_API_URL must be an absolute http(s) URL")


def _normalize_base_url(value: str) -> str:
    base = value.strip() or "/"
    if not base.startswith("/"):
        raise ConfigError("NBLAUNCH_JUPYTERHUB_BASE_URL must start with '/'")
    if len(base) > 1 and base.endswith("/"):
        return base[:-1]
    return base


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env_map = os_environ if env is None else env

    hmac_secret = _required(env_map, "NBLAUNCH_HMAC_SECRET")
    service_token = _required(env_map, "NBLAUNCH_SERVICE_TOKEN")
    hub_api_url = _required(env_map, "NBLAUNCH_HUB_API_URL")
    notebook_base_dir = _required(env_map, "NBLAUNCH_NOTEBOOK_BASE_DIR")

    if not isabs(notebook_base_dir):
        raise ConfigError("NBLAUNCH_NOTEBOOK_BASE_DIR must be an absolute path")

    _validate_hub_api_url(hub_api_url)

    return Settings(
        hmac_secret=hmac_secret,
        service_token=service_token,
        hub_api_url=hub_api_url,
        notebook_base_dir=notebook_base_dir,
        signature_ttl_seconds=_int_setting(env_map, "NBLAUNCH_SIGNATURE_TTL_SECONDS", 300),
        max_notebook_bytes=_int_setting(env_map, "NBLAUNCH_MAX_NOTEBOOK_BYTES", 10 * 1024 * 1024),
        gallery_timeout_seconds=_int_setting(env_map, "NBLAUNCH_GALLERY_TIMEOUT_SECONDS", 10),
        http_timeout_seconds=_int_setting(env_map, "NBLAUNCH_HTTP_TIMEOUT_SECONDS", 10),
        log_level=(env_map.get("NBLAUNCH_LOG_LEVEL", "INFO") or "INFO").upper(),
        jupyterhub_base_url=_normalize_base_url(env_map.get("NBLAUNCH_JUPYTERHUB_BASE_URL", "/")),
    )
