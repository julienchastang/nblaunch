"""Application factory for nblaunch."""

from __future__ import annotations

from fastapi import FastAPI

from .config import Settings, load_settings
from .handlers import healthz, launch, oauth_callback_placeholder
from .nbgallery import fetch_notebook
from .storage import write_notebook


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or load_settings()
    app = FastAPI(title="nblaunch")
    app.state.settings = app_settings
    app.state.resolve_user_root = None
    app.state.gallery_base_url = "http://127.0.0.1:9"
    app.state.fetch_notebook = fetch_notebook
    app.state.write_notebook = write_notebook

    app.add_api_route("/healthz", healthz, methods=["GET"])
    app.add_api_route("/launch", launch, methods=["GET"])
    app.add_api_route("/oauth_callback", oauth_callback_placeholder, methods=["GET"])

    return app
