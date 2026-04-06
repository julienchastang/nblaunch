"""Filesystem storage primitives for nblaunch notebooks."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile


class StorageError(RuntimeError):
    """Raised when notebook storage fails."""


class UserRootResolutionError(StorageError):
    """Raised when a username cannot be mapped to a storage path."""


@dataclass(frozen=True)
class StoredNotebook:
    absolute_path: Path
    relative_path: str


def _safe_home_subpath(home_subpath: str) -> Path:
    raw = home_subpath.strip()
    if not raw:
        raise StorageError("home subpath must not be empty")

    target = Path(raw)
    if target.is_absolute():
        raise StorageError("home subpath must be relative")

    normalized = Path(os.path.normpath(raw))
    if str(normalized) in {"", "."}:
        raise StorageError("home subpath must not be empty")
    if any(part in {"..", ""} for part in normalized.parts):
        raise StorageError("home subpath contains traversal")
    return normalized


def resolve_user_root_from_home_subpath(*, base_dir: Path, home_subpath: str) -> Path:
    return base_dir / _safe_home_subpath(home_subpath)


def resolve_user_root(*, notebook_base_dir: str | Path, username: str) -> Path:
    try:
        return resolve_user_root_from_home_subpath(
            base_dir=Path(notebook_base_dir),
            home_subpath=username,
        )
    except StorageError as exc:
        raise UserRootResolutionError("invalid username for local storage resolution") from exc


def _safe_notebook_relative_path(notebook_id: str) -> Path:
    target = Path("nbgallery") / f"{notebook_id}.ipynb"
    if target.is_absolute():
        raise StorageError("notebook path must be relative")

    if any(part == ".." for part in target.parts):
        raise StorageError("notebook path contains parent traversal")
    normalized = Path(os.path.normpath(str(target)))
    if normalized.parts and normalized.parts[0] != "nbgallery":
        raise StorageError("notebook path escapes storage namespace")
    return normalized


def planned_notebook_path(*, user_root: Path, notebook_id: str) -> Path:
    return user_root / _safe_notebook_relative_path(notebook_id)


def write_notebook(*, user_root: Path, notebook_id: str, notebook_bytes: bytes) -> StoredNotebook:
    relative_path = _safe_notebook_relative_path(notebook_id)
    destination = planned_notebook_path(user_root=user_root, notebook_id=notebook_id)

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=".nblaunch-",
            delete=False,
        ) as tmp_file:
            tmp_file.write(notebook_bytes)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
            tmp_name = tmp_file.name
        os.replace(tmp_name, destination)
    except OSError as exc:
        raise StorageError("failed to write notebook to storage") from exc

    return StoredNotebook(
        absolute_path=destination,
        relative_path=relative_path.as_posix(),
    )
