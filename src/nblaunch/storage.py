"""Filesystem storage primitives for nblaunch notebooks."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile


class StorageError(RuntimeError):
    """Raised when notebook storage fails."""


@dataclass(frozen=True)
class StoredNotebook:
    absolute_path: Path
    relative_path: str


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


def write_notebook(*, user_root: Path, notebook_id: str, notebook_bytes: bytes) -> StoredNotebook:
    relative_path = _safe_notebook_relative_path(notebook_id)
    destination = user_root / relative_path

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
