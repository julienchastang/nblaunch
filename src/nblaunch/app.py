"""Application factory for nblaunch."""

from __future__ import annotations

from fastapi import FastAPI

from .config import Settings, load_settings
from .handlers import healthz, launch_placeholder, oauth_callback_placeholder


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or load_settings()
    app = FastAPI(title="nblaunch")
    app.state.settings = app_settings

    app.add_api_route("/healthz", healthz, methods=["GET"])
    app.add_api_route("/launch", launch_placeholder, methods=["GET"])
    app.add_api_route("/oauth_callback", oauth_callback_placeholder, methods=["GET"])

    return app
