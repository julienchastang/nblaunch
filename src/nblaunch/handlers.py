"""HTTP handlers for nblaunch routes."""

from __future__ import annotations

from typing import Protocol, cast
from pathlib import Path

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from .config import Settings
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
        timeout_seconds: int,
        max_bytes: int,
    ) -> NotebookPayload:
        ...


class NotebookWriter(Protocol):
    def __call__(self, *, user_root: Path, notebook_id: str, notebook_bytes: bytes) -> StoredNotebook:
        ...


class UserRootResolver(Protocol):
    def __call__(self, request: Request) -> Path | str:
        ...


class AppState(Protocol):
    settings: Settings
    resolve_user_root: UserRootResolver | None
    gallery_base_url: str
    fetch_notebook: NotebookFetcher
    write_notebook: NotebookWriter


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


def _resolve_user_root(request: Request, settings: Settings) -> Path:
    resolver = _app_state(request).resolve_user_root
    if resolver is not None:
        return Path(resolver(request))

    header_value = request.headers.get("X-NBLaunch-User-Root")
    if header_value:
        return Path(header_value)

    # Provisional Stage 04 default prior to Hub user-home resolution wiring.
    return Path(settings.notebook_base_dir) / "provisional-user"


def _redirect_location(base_url: str, relative_notebook_path: str) -> str:
    prefix = base_url if base_url != "/" else ""
    return f"{prefix}/user-redirect/lab/tree/{relative_notebook_path}"


async def launch(request: Request) -> Response:
    state = _app_state(request)
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
    fetcher = state.fetch_notebook
    writer = state.write_notebook

    try:
        payload = fetcher(
            base_url=gallery_base_url,
            notebook_id=validated.notebook_id,
            timeout_seconds=settings.gallery_timeout_seconds,
            max_bytes=settings.max_notebook_bytes,
        )
    except GalleryTooLargeError as exc:
        return _error_response(status.HTTP_413_CONTENT_TOO_LARGE, "notebook_too_large", str(exc))
    except (GalleryTimeoutError, GalleryUpstreamError, GalleryContentTypeError) as exc:
        return _error_response(status.HTTP_502_BAD_GATEWAY, "gallery_fetch_failed", str(exc))

    user_root = _resolve_user_root(request, settings)
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


async def oauth_callback_placeholder() -> Response:
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)
