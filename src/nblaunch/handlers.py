"""HTTP handlers for nblaunch routes."""

from __future__ import annotations

from fastapi import Response, status


async def healthz() -> dict[str, bool]:
    return {"ok": True}


async def launch_placeholder() -> Response:
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


async def oauth_callback_placeholder() -> Response:
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)
