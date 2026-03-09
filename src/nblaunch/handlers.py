"""HTTP handlers for nblaunch routes."""

from __future__ import annotations

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from .security import ValidationError, validate_launch_request


async def healthz() -> dict[str, bool]:
    return {"ok": True}


def _error_status_for(kind: str) -> int:
    if kind in {"missing_params", "malformed_params", "invalid_notebook_id", "invalid_timestamp"}:
        return status.HTTP_400_BAD_REQUEST
    if kind in {"invalid_timestamp_window", "invalid_signature"}:
        return status.HTTP_401_UNAUTHORIZED
    return status.HTTP_400_BAD_REQUEST


async def launch(request: Request) -> Response:
    settings = request.app.state.settings
    query = request.query_params

    try:
        validate_launch_request(
            nb=query.get("nb"),
            ts=query.get("ts"),
            sig=query.get("sig"),
            secret=settings.hmac_secret,
            ttl_seconds=settings.signature_ttl_seconds,
        )
    except ValidationError as exc:
        return JSONResponse(
            status_code=_error_status_for(exc.kind),
            content={"error": {"code": exc.kind, "message": exc.message}},
        )

    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


async def oauth_callback_placeholder() -> Response:
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)
