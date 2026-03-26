from __future__ import annotations
# pyright: reportMissingTypeStubs=false

from email.message import Message
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from nblaunch.nbgallery import (
    GalleryContentTypeError,
    GalleryTimeoutError,
    GalleryTooLargeError,
    GalleryUpstreamError,
    fetch_notebook,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class FakeResponse:
    _body: bytes
    _offset: int

    def __init__(self, body: bytes, content_type: str = "application/json", content_length: int | None = None):
        self._body = body
        self._offset = 0
        self.headers: dict[str, str] = {"Content-Type": content_type}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._body) - self._offset
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


def _request_url(request: Request | str) -> str:
    if isinstance(request, Request):
        return request.full_url
    return request


def test_fetch_notebook_happy_path() -> None:
    notebook_bytes = (FIXTURES / "sample_notebook.ipynb").read_bytes()

    def _opener(request: Request | str, timeout: int) -> FakeResponse:
        url = _request_url(request)
        assert "/api/notebooks/gallery/notebook.ipynb" in url
        assert isinstance(request, Request)
        assert request.get_header("User-agent") == (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        assert timeout == 3
        return FakeResponse(notebook_bytes, content_type="application/x-ipynb+json")

    payload = fetch_notebook(
        base_url="https://gallery.example",
        notebook_id="gallery/notebook.ipynb",
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        timeout_seconds=3,
        max_bytes=1024 * 128,
        opener=_opener,
    )

    assert payload.notebook_id == "gallery/notebook.ipynb"
    assert payload.content == notebook_bytes


def test_fetch_notebook_uses_configured_download_template() -> None:
    notebook_bytes = (FIXTURES / "sample_notebook.ipynb").read_bytes()

    def _opener(request: Request | str, timeout: int) -> FakeResponse:
        url = _request_url(request)
        assert "/notebooks/gallery/notebook.ipynb/download?clickstream=false" in url
        assert isinstance(request, Request)
        assert request.get_header("User-agent") == "custom-agent/1.0"
        assert timeout == 3
        return FakeResponse(notebook_bytes, content_type="application/octet-stream")

    payload = fetch_notebook(
        base_url="https://gallery.example",
        notebook_id="gallery/notebook.ipynb",
        path_template="/notebooks/{notebook_id}/download?clickstream=false",
        user_agent="custom-agent/1.0",
        timeout_seconds=3,
        max_bytes=1024 * 128,
        opener=_opener,
    )

    assert payload.notebook_id == "gallery/notebook.ipynb"
    assert payload.content == notebook_bytes


def test_fetch_notebook_rejects_html_content_type() -> None:
    body = (FIXTURES / "bad_html_response.html").read_bytes()

    def _opener(request: Request | str, timeout: int) -> FakeResponse:
        _ = (request, timeout)
        return FakeResponse(body, content_type="text/html")

    with pytest.raises(GalleryContentTypeError, match="text/html"):
        _ = fetch_notebook(
            base_url="https://gallery.example",
            notebook_id="gallery/notebook.ipynb",
            user_agent="test-agent",
            timeout_seconds=3,
            max_bytes=1024 * 128,
            opener=_opener,
        )


def test_fetch_notebook_rejects_oversized_header() -> None:
    body = (FIXTURES / "sample_notebook.ipynb").read_bytes()

    def _opener(request: Request | str, timeout: int) -> FakeResponse:
        _ = (request, timeout)
        return FakeResponse(body, content_length=(1024 * 1024))

    with pytest.raises(GalleryTooLargeError, match="exceeds max size"):
        _ = fetch_notebook(
            base_url="https://gallery.example",
            notebook_id="gallery/notebook.ipynb",
            user_agent="test-agent",
            timeout_seconds=3,
            max_bytes=128,
            opener=_opener,
        )


def test_fetch_notebook_rejects_oversized_payload() -> None:
    # Generate oversized content in-memory so no large fixture file is needed.
    body = b"x" * 2048

    def _opener(request: Request | str, timeout: int) -> FakeResponse:
        _ = (request, timeout)
        return FakeResponse(body)

    with pytest.raises(GalleryTooLargeError, match="exceeds max size"):
        _ = fetch_notebook(
            base_url="https://gallery.example",
            notebook_id="gallery/notebook.ipynb",
            user_agent="test-agent",
            timeout_seconds=3,
            max_bytes=1024,
            opener=_opener,
        )


def test_fetch_notebook_maps_timeout() -> None:
    def _opener(request: Request | str, timeout: int) -> FakeResponse:
        _ = (request, timeout)
        raise URLError("timed out")

    with pytest.raises(GalleryTimeoutError):
        _ = fetch_notebook(
            base_url="https://gallery.example",
            notebook_id="gallery/notebook.ipynb",
            user_agent="test-agent",
            timeout_seconds=3,
            max_bytes=1024,
            opener=_opener,
        )


def test_fetch_notebook_maps_http_error() -> None:
    def _opener(request: Request | str, timeout: int) -> FakeResponse:
        _ = timeout
        raise HTTPError(url=_request_url(request), code=502, msg="bad gateway", hdrs=Message(), fp=None)

    with pytest.raises(GalleryUpstreamError, match="HTTP 502"):
        _ = fetch_notebook(
            base_url="https://gallery.example",
            notebook_id="gallery/notebook.ipynb",
            user_agent="test-agent",
            timeout_seconds=3,
            max_bytes=1024,
            opener=_opener,
        )
