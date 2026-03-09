"""Security and validation primitives for launch requests."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import re
import time
from collections.abc import Callable


_NOTEBOOK_ID_RE = re.compile(r"^[A-Za-z0-9._/-]{1,256}$")
_SIGNATURE_RE = re.compile(r"^[a-f0-9]{64}$")


class ValidationError(ValueError):
    """Raised when launch-request validation fails."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass(frozen=True)
class LaunchRequest:
    notebook_id: str
    timestamp: int
    signature: str


def canonical_message(notebook_id: str, timestamp: int) -> str:
    return f"{notebook_id}:{timestamp}"


def sign_message(secret: str, notebook_id: str, timestamp: int) -> str:
    message = canonical_message(notebook_id, timestamp).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def validate_launch_request(
    *,
    nb: str | None,
    ts: str | None,
    sig: str | None,
    secret: str,
    ttl_seconds: int,
    now_seconds: Callable[[], int] | None = None,
) -> LaunchRequest:
    if not nb or not ts or not sig:
        raise ValidationError("missing_params", "missing required query params: nb, ts, sig")

    if not _NOTEBOOK_ID_RE.fullmatch(nb):
        raise ValidationError("malformed_params", "nb is malformed")
    if ".." in nb or nb.startswith("/") or "://" in nb:
        raise ValidationError("invalid_notebook_id", "nb contains forbidden path or scheme patterns")

    try:
        ts_value = int(ts)
    except ValueError as exc:
        raise ValidationError("invalid_timestamp", "ts must be an integer unix epoch value") from exc

    if not _SIGNATURE_RE.fullmatch(sig):
        raise ValidationError("malformed_params", "sig must be a lowercase 64-char hex sha256 digest")

    now_fn = now_seconds or (lambda: int(time.time()))
    now_value = now_fn()
    if abs(now_value - ts_value) > ttl_seconds:
        raise ValidationError("invalid_timestamp_window", "timestamp is outside allowed ttl window")

    expected_sig = sign_message(secret, nb, ts_value)
    if not hmac.compare_digest(expected_sig, sig):
        raise ValidationError("invalid_signature", "signature mismatch")

    return LaunchRequest(notebook_id=nb, timestamp=ts_value, signature=sig)
