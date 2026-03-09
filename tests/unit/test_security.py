from __future__ import annotations

import hmac

import pytest

from nblaunch.security import ValidationError, canonical_message, sign_message, validate_launch_request


def test_canonical_message_format_is_nb_colon_ts() -> None:
    assert canonical_message("catalog/notebook.ipynb", 1700000000) == "catalog/notebook.ipynb:1700000000"


def test_validate_launch_request_rejects_missing_params() -> None:
    with pytest.raises(ValidationError, match="missing required query params"):
        validate_launch_request(
            nb=None,
            ts="1700000000",
            sig="a" * 64,
            secret="secret",
            ttl_seconds=300,
            now_seconds=lambda: 1700000000,
        )


def test_validate_launch_request_rejects_invalid_notebook_id() -> None:
    sig = sign_message("secret", "../escape.ipynb", 1700000000)
    with pytest.raises(ValidationError, match="forbidden path"):
        validate_launch_request(
            nb="../escape.ipynb",
            ts="1700000000",
            sig=sig,
            secret="secret",
            ttl_seconds=300,
            now_seconds=lambda: 1700000000,
        )


def test_validate_launch_request_rejects_invalid_timestamp() -> None:
    with pytest.raises(ValidationError, match="integer unix epoch"):
        validate_launch_request(
            nb="valid/path.ipynb",
            ts="nope",
            sig="a" * 64,
            secret="secret",
            ttl_seconds=300,
            now_seconds=lambda: 1700000000,
        )


def test_validate_launch_request_rejects_expired_or_future_timestamp() -> None:
    timestamp = 1700000000
    sig = sign_message("secret", "valid/path.ipynb", timestamp)
    with pytest.raises(ValidationError, match="outside allowed ttl"):
        validate_launch_request(
            nb="valid/path.ipynb",
            ts=str(timestamp),
            sig=sig,
            secret="secret",
            ttl_seconds=300,
            now_seconds=lambda: timestamp + 301,
        )


def test_validate_launch_request_rejects_invalid_signature() -> None:
    with pytest.raises(ValidationError, match="signature mismatch"):
        validate_launch_request(
            nb="valid/path.ipynb",
            ts="1700000000",
            sig="0" * 64,
            secret="secret",
            ttl_seconds=300,
            now_seconds=lambda: 1700000000,
        )


def test_validate_launch_request_uses_constant_time_compare(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    original_compare_digest = hmac.compare_digest

    def _spy(left: str, right: str) -> bool:
        calls.append((left, right))
        return original_compare_digest(left, right)

    monkeypatch.setattr("nblaunch.security.hmac.compare_digest", _spy)

    timestamp = 1700000000
    nb = "valid/path.ipynb"
    sig = sign_message("secret", nb, timestamp)
    result = validate_launch_request(
        nb=nb,
        ts=str(timestamp),
        sig=sig,
        secret="secret",
        ttl_seconds=300,
        now_seconds=lambda: timestamp,
    )

    assert result.notebook_id == nb
    assert calls == [(sig, sig)]
