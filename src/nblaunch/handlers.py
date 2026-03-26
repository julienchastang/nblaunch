"""HTTP handlers for nblaunch routes."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, cast

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from .config import Settings
from .hubapi import HomeSubpathNotFoundError, HubApiError
from .nbgallery import (
    GalleryContentTypeError,
    NotebookPayload,
    GalleryTimeoutError,
    GalleryTooLargeError,
    GalleryUpstreamError,
)
from .security import ValidationError, validate_launch_request
from .storage import StorageError, StoredNotebook


class NotebookFetcher(Protocol):
    def __call__(
        self,
        *,
        base_url: str,
        notebook_id: str,
        path_template: str,
        user_agent: str,
        timeout_seconds: int,
        max_bytes: int,
    ) -> NotebookPayload:
        ...


class NotebookWriter(Protocol):
    def __call__(self, *, user_root: Path, notebook_id: str, notebook_bytes: bytes) -> StoredNotebook:
        ...


class UserRootResolver(Protocol):
    def __call__(self, *, request: Request, username: str, settings: Settings) -> Path | str:
        ...


class ServiceAuth(Protocol):
    def current_user(self, request: Request) -> str | None:
        ...

    def login_redirect(self, request: Request) -> Response:
        ...

    async def oauth_callback(self, request: Request) -> Response:
        ...


class AppState(Protocol):
    settings: Settings
    resolve_user_root: UserRootResolver | None
    gallery_base_url: str
    gallery_download_path_template: str
    gallery_user_agent: str
    fetch_notebook: NotebookFetcher
    write_notebook: NotebookWriter
    service_auth: ServiceAuth


async def healthz() -> dict[str, bool]:
    return {"ok": True}


def _error_status_for(kind: str) -> int:
    if kind in {"missing_params", "malformed_params", "invalid_notebook_id", "invalid_timestamp"}:
        return status.HTTP_400_BAD_REQUEST
    if kind in {"invalid_timestamp_window", "invalid_signature"}:
        return status.HTTP_401_UNAUTHORIZED
    return status.HTTP_400_BAD_REQUEST


def _error_response(http_status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": code, "message": message}},
    )


def _app_state(request: Request) -> AppState:
    return cast(AppState, request.app.state)


def _resolve_user_root(request: Request, settings: Settings, username: str) -> Path:
    resolver = _app_state(request).resolve_user_root
    if resolver is None:
        raise HubApiError("user-root resolver is not configured")
    return Path(resolver(request=request, username=username, settings=settings))


def _redirect_location(base_url: str, relative_notebook_path: str) -> str:
    prefix = base_url if base_url != "/" else ""
    return f"{prefix}/user-redirect/lab/tree/{relative_notebook_path}"


async def launch(request: Request) -> Response:
    state = _app_state(request)
    username = state.service_auth.current_user(request)
    if username is None:
        return state.service_auth.login_redirect(request)

    settings = state.settings
    query = request.query_params

    try:
        validated = validate_launch_request(
            nb=query.get("nb"),
            ts=query.get("ts"),
            sig=query.get("sig"),
            secret=settings.hmac_secret,
            ttl_seconds=settings.signature_ttl_seconds,
        )
    except ValidationError as exc:
        return _error_response(_error_status_for(exc.kind), exc.kind, exc.message)

    gallery_base_url = state.gallery_base_url
    gallery_download_path_template = state.gallery_download_path_template
    gallery_user_agent = state.gallery_user_agent
    fetcher = state.fetch_notebook
    writer = state.write_notebook

    try:
        payload = fetcher(
            base_url=gallery_base_url,
            notebook_id=validated.notebook_id,
            path_template=gallery_download_path_template,
            user_agent=gallery_user_agent,
            timeout_seconds=settings.gallery_timeout_seconds,
            max_bytes=settings.max_notebook_bytes,
        )
    except GalleryTooLargeError as exc:
        return _error_response(status.HTTP_413_CONTENT_TOO_LARGE, "notebook_too_large", str(exc))
    except (GalleryTimeoutError, GalleryUpstreamError, GalleryContentTypeError) as exc:
        return _error_response(status.HTTP_502_BAD_GATEWAY, "gallery_fetch_failed", str(exc))

    try:
        user_root = _resolve_user_root(request, settings, username)
    except HomeSubpathNotFoundError as exc:
        return _error_response(status.HTTP_404_NOT_FOUND, "missing_user_home_mapping", str(exc))
    except HubApiError as exc:
        return _error_response(status.HTTP_502_BAD_GATEWAY, "hub_home_lookup_failed", str(exc))

    try:
        stored = writer(
            user_root=user_root,
            notebook_id=validated.notebook_id,
            notebook_bytes=payload.content,
        )
    except StorageError as exc:
        return _error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, "storage_write_failed", str(exc))

    return Response(
        status_code=status.HTTP_302_FOUND,
        headers={"Location": _redirect_location(settings.jupyterhub_base_url, stored.relative_path)},
    )


async def oauth_callback_placeholder(request: Request) -> Response:
    return await _app_state(request).service_auth.oauth_callback(request)
