"""Notebook retrieval primitives for nblaunch."""

from __future__ import annotations

from dataclasses import dataclass
from socket import timeout as SocketTimeout
from collections.abc import Callable, Mapping
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class GalleryResponse(Protocol):
    headers: Mapping[str, str]

    def read(self, size: int = -1) -> bytes:
        ...

    def __enter__(self) -> "GalleryResponse":
        ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        ...


class GalleryError(RuntimeError):
    """Base class for gallery download failures."""


class GalleryTimeoutError(GalleryError):
    """Raised when gallery fetch times out."""


class GalleryUpstreamError(GalleryError):
    """Raised when gallery returns non-success or transport errors."""


class GalleryContentTypeError(GalleryError):
    """Raised when upstream returns unexpected content type."""


class GalleryTooLargeError(GalleryError):
    """Raised when upstream payload exceeds configured size limit."""


@dataclass(frozen=True)
class NotebookPayload:
    notebook_id: str
    content: bytes
    content_type: str


def _build_notebook_url(base_url: str, notebook_id: str, path_template: str) -> str:
    encoded = quote(notebook_id, safe="/._-")
    return f"{base_url.rstrip('/')}{path_template.format(notebook_id=encoded)}"


def _content_type(headers: dict[str, str]) -> str:
    value = headers.get("Content-Type", "")
    return value.split(";")[0].strip().lower()


def fetch_notebook(
    *,
    base_url: str,
    notebook_id: str,
    path_template: str = "/api/notebooks/{notebook_id}",
    user_agent: str,
    timeout_seconds: int,
    max_bytes: int,
    opener: Callable[..., object] | None = None,
) -> NotebookPayload:
    open_fn = urlopen if opener is None else opener
    url = _build_notebook_url(base_url, notebook_id, path_template)
    request = Request(url, headers={"User-Agent": user_agent})

    try:
        with cast(GalleryResponse, open_fn(request, timeout=timeout_seconds)) as response:
            headers = dict(response.headers)
            content_type = _content_type(headers)
            if content_type == "text/html":
                raise GalleryContentTypeError("gallery response content-type text/html is not allowed")

            content_length = headers.get("Content-Length")
            if content_length is not None:
                try:
                    header_size = int(content_length)
                except ValueError as exc:
                    raise GalleryUpstreamError("gallery returned invalid content-length header") from exc
                if header_size > max_bytes:
                    raise GalleryTooLargeError("gallery payload exceeds max size")

            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise GalleryTooLargeError("gallery payload exceeds max size")
                chunks.append(chunk)
    except GalleryError:
        raise
    except HTTPError as exc:
        raise GalleryUpstreamError(f"gallery returned HTTP {exc.code}") from exc
    except (URLError, SocketTimeout, TimeoutError) as exc:
        raise GalleryTimeoutError("gallery request timed out or failed") from exc
    except OSError as exc:
        raise GalleryUpstreamError("gallery request transport error") from exc

    return NotebookPayload(notebook_id=notebook_id, content=b"".join(chunks), content_type=content_type)
