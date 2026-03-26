"""Application factory for nblaunch."""

from __future__ import annotations

import logging
import secrets
from pathlib import Path
from json import JSONDecodeError, loads
from typing import cast
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError, URLError

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from .config import Settings, load_settings
from .hubapi import resolve_user_root as resolve_hub_user_root
from .handlers import healthz, launch, oauth_callback_placeholder
from .nbgallery import fetch_notebook
from .storage import write_notebook


SERVICE_NAME = "nblaunch"
SERVICE_URL = "http://nblaunch:8000"
SERVICE_PREFIX = "/services/nblaunch"
SERVICE_OAUTH_CLIENT_ID = "service-nblaunch"
SERVICE_CALLBACK_PATH = "/oauth_callback"
HUB_AUTHORIZE_PATH = "/api/oauth2/authorize"
HUB_TOKEN_PATH = "/api/oauth2/token"
HUB_USER_PATH = "/api/user"
_USER_COOKIE = "nblaunch-user"
_STATE_COOKIE = "nblaunch-oauth-state"
_NEXT_COOKIE = "nblaunch-oauth-next"
_LEGACY_PLACEHOLDER_USER = "oauth-authenticated-user"
_FORWARDED_USER_HEADERS = (
    "X-Forwarded-User",
    "X-Auth-Request-User",
    "Remote-User",
)


logger = logging.getLogger(__name__)


def _hub_path(base_url: str, suffix: str) -> str:
    prefix = "" if base_url == "/" else base_url
    return f"{prefix}{suffix}"


def _resolved_username(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    username = value.strip().strip('"')
    if not username or username == _LEGACY_PLACEHOLDER_USER:
        return None
    return username


async def service_root() -> dict[str, str]:
    return {"service": SERVICE_NAME, "status": "ok"}


class JupyterHubServiceAuth:
    _authorize_url: str
    _callback_url: str
    _service_root: str
    _hub_token_url: str
    _hub_user_url: str
    _http_timeout_seconds: int
    _service_token: str

    def __init__(self, settings: Settings) -> None:
        self._authorize_url = _hub_path(settings.jupyterhub_base_url, HUB_AUTHORIZE_PATH)
        self._callback_url = f"{SERVICE_PREFIX}{SERVICE_CALLBACK_PATH}"
        self._service_root = SERVICE_PREFIX
        self._hub_token_url = self._hub_api_url(settings, HUB_TOKEN_PATH)
        self._hub_user_url = self._hub_api_url(settings, HUB_USER_PATH)
        self._http_timeout_seconds = settings.http_timeout_seconds
        self._service_token = settings.service_token

    @staticmethod
    def _hub_api_url(settings: Settings, path: str) -> str:
        hub_api_url = settings.hub_api_url.rstrip("/")
        api_base = _hub_path(settings.jupyterhub_base_url, "/api")
        if hub_api_url.endswith(api_base):
            hub_origin = hub_api_url[: -len(api_base)]
        else:
            hub_origin = hub_api_url
        return f"{hub_origin}{_hub_path(settings.jupyterhub_base_url, path)}"

    def _json_request(
        self,
        *,
        url: str,
        headers: dict[str, str],
        data: bytes | None = None,
    ) -> object | None:
        hub_request = UrlRequest(url, headers=headers, data=data)
        try:
            with urlopen(hub_request, timeout=self._http_timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except (HTTPError, URLError, OSError):
            return None

        try:
            return cast(object, loads(payload))
        except JSONDecodeError:
            return None

    def _oauth_authenticated_user(self, code: str) -> str | None:
        token_payload = urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._callback_url,
                "client_id": SERVICE_OAUTH_CLIENT_ID,
                "client_secret": self._service_token,
            }
        ).encode("utf-8")
        token_response = self._json_request(
            url=self._hub_token_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=token_payload,
        )
        logger.info(
            "nblaunch auth _oauth_authenticated_user token_url=%r token_response=%r",
            self._hub_token_url,
            token_response,
        )
        if not isinstance(token_response, dict):
            return None

        access_token = token_response.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            return None

        user_response = self._json_request(
            url=self._hub_user_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"token {access_token}",
            },
        )
        logger.info(
            "nblaunch auth _oauth_authenticated_user hub_user_url=%r user_response=%r",
            self._hub_user_url,
            user_response,
        )
        if not isinstance(user_response, dict):
            return None
        return _resolved_username(user_response.get("name"))

    def _hub_authenticated_user(self, request: Request) -> str | None:
        cookie_header = request.headers.get("cookie")
        forwarded_user: str | None = None
        for header_name in _FORWARDED_USER_HEADERS:
            header_value = _resolved_username(request.headers.get(header_name))
            if header_value is not None:
                forwarded_user = header_value
                break

        logger.info(
            "nblaunch auth _hub_authenticated_user hub_user_url=%r cookies_forwarded=%r incoming_cookies=%r forwarded_headers=%r",
            self._hub_user_url,
            bool(cookie_header),
            dict(request.cookies),
            {header_name: request.headers.get(header_name) for header_name in _FORWARDED_USER_HEADERS},
        )

        if not cookie_header:
            if forwarded_user is not None:
                logger.info(
                    "nblaunch auth _hub_authenticated_user resolved from forwarded header username=%r",
                    forwarded_user,
                )
                return forwarded_user
            logger.info("nblaunch auth _hub_authenticated_user no cookies or forwarded user")
            return None

        data = self._json_request(
            url=self._hub_user_url,
            headers={
                "Accept": "application/json",
                "Cookie": cookie_header,
            },
        )
        if data is None:
            logger.info(
                "nblaunch auth hub-user lookup failed cookies=%r hub_user_url=%r",
                dict(request.cookies),
                self._hub_user_url,
            )
            return forwarded_user

        logger.info(
            "nblaunch auth _hub_authenticated_user hub_user_url=%r raw_payload=%r",
            self._hub_user_url,
            data,
        )

        if not isinstance(data, dict):
            if forwarded_user is not None:
                logger.info(
                    "nblaunch auth _hub_authenticated_user falling back to forwarded header after non-dict hub payload username=%r",
                    forwarded_user,
                )
            return forwarded_user
        data_dict = cast(dict[str, object], data)
        resolved = _resolved_username(data_dict.get("name"))
        logger.info(
            "nblaunch auth _hub_authenticated_user resolved from hub api username=%r",
            resolved,
        )
        if resolved is not None:
            return resolved

        if forwarded_user is not None:
            logger.info(
                "nblaunch auth _hub_authenticated_user falling back to forwarded header after empty hub username=%r",
                forwarded_user,
            )
        return forwarded_user

    def current_user(self, request: Request) -> str | None:
        cookie_user = _resolved_username(request.cookies.get(_USER_COOKIE))
        hub_user = self._hub_authenticated_user(request)
        resolved = hub_user or cookie_user
        logger.info(
            "nblaunch auth current_user incoming cookies=%r cookie_user=%r hub_user=%r resolved_username=%r",
            dict(request.cookies),
            cookie_user,
            hub_user,
            resolved,
        )
        return resolved

    def login_redirect(self, request: Request) -> Response:
        oauth_state = secrets.token_urlsafe(24)
        next_url = request.url.path
        if request.url.query:
            next_url = f"{next_url}?{request.url.query}"

        params = urlencode(
            {
                "client_id": SERVICE_OAUTH_CLIENT_ID,
                "redirect_uri": self._callback_url,
                "response_type": "code",
                "state": oauth_state,
            }
        )
        response = RedirectResponse(url=f"{self._authorize_url}?{params}", status_code=status.HTTP_302_FOUND)
        response.set_cookie(_STATE_COOKIE, oauth_state, httponly=True, samesite="lax")
        response.set_cookie(_NEXT_COOKIE, next_url, httponly=True, samesite="lax")
        return response

    async def oauth_callback(self, request: Request) -> Response:
        state = request.query_params.get("state")
        code = request.query_params.get("code")
        expected_state = request.cookies.get(_STATE_COOKIE)
        if not code or not isinstance(expected_state, str) or state != expected_state:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": {
                        "code": "oauth_callback_failed",
                        "message": "unable to establish authenticated service context",
                    }
                },
            )

        username = self._oauth_authenticated_user(code)
        logger.info(
            "nblaunch auth oauth_callback incoming cookies=%r code_present=%r resolved_username=%r",
            dict(request.cookies),
            bool(code),
            username,
        )
        if username is None:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": {
                        "code": "oauth_callback_failed",
                        "message": "unable to resolve authenticated JupyterHub user",
                    }
                },
            )

        redirect_target = request.cookies.get(_NEXT_COOKIE) or self._service_root
        response = RedirectResponse(url=redirect_target, status_code=status.HTTP_302_FOUND)
        response.delete_cookie(_STATE_COOKIE)
        response.delete_cookie(_NEXT_COOKIE)
        response.set_cookie(_USER_COOKIE, username, httponly=True, samesite="lax")
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or load_settings()
    app = FastAPI(title="nblaunch")

    def _resolve_user_root(*, request: Request, username: str, settings: Settings) -> Path:
        _ = request
        return resolve_hub_user_root(
            hub_api_url=settings.hub_api_url,
            service_token=settings.service_token,
            notebook_base_dir=settings.notebook_base_dir,
            username=username,
            timeout_seconds=settings.http_timeout_seconds,
        )

    app.state.settings = app_settings
    app.state.resolve_user_root = _resolve_user_root
    app.state.gallery_base_url = app_settings.gallery_base_url
    app.state.gallery_download_path_template = app_settings.gallery_download_path_template
    app.state.gallery_user_agent = app_settings.gallery_user_agent
    app.state.fetch_notebook = fetch_notebook
    app.state.write_notebook = write_notebook
    app.state.service_auth = JupyterHubServiceAuth(app_settings)

    app.add_api_route("/", service_root, methods=["GET"])
    app.add_api_route("/healthz", healthz, methods=["GET"])
    app.add_api_route("/launch", launch, methods=["GET"])
    app.add_api_route("/oauth_callback", oauth_callback_placeholder, methods=["GET"])
    app.add_api_route(f"{SERVICE_PREFIX}/", service_root, methods=["GET"])
    app.add_api_route(f"{SERVICE_PREFIX}/healthz", healthz, methods=["GET"])
    app.add_api_route(f"{SERVICE_PREFIX}/launch", launch, methods=["GET"])
    app.add_api_route(f"{SERVICE_PREFIX}/oauth_callback", oauth_callback_placeholder, methods=["GET"])

    return app
