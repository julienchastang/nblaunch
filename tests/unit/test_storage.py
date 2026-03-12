from __future__ import annotations

from pathlib import Path

import pytest

from nblaunch.storage import StorageError, write_notebook


def test_write_notebook_writes_under_expected_path(tmp_path: Path) -> None:
    stored = write_notebook(
        user_root=tmp_path,
        notebook_id="gallery/notebook",
        notebook_bytes=b'{"cells":[]}',
    )

    assert stored.relative_path == "nbgallery/gallery/notebook.ipynb"
    assert stored.absolute_path == tmp_path / "nbgallery" / "gallery" / "notebook.ipynb"
    assert stored.absolute_path.read_bytes() == b'{"cells":[]}'


def test_write_notebook_rejects_traversal() -> None:
    with pytest.raises(StorageError, match="traversal|escapes"):
        write_notebook(
            user_root=Path("/tmp/user-root"),
            notebook_id="../escape",
            notebook_bytes=b"{}",
        )


def test_write_notebook_is_atomic_and_replaces_existing(tmp_path: Path) -> None:
    existing = tmp_path / "nbgallery" / "gallery" / "notebook.ipynb"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"old")

    stored = write_notebook(
        user_root=tmp_path,
        notebook_id="gallery/notebook",
        notebook_bytes=b"new",
    )

    assert stored.absolute_path == existing
    assert existing.read_bytes() == b"new"
