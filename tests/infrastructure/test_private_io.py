"""Private file I/O: atomic replacement and owner-only append streams."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from folionym.infrastructure.private_io import atomic_write_private_text, open_private_append_text


@pytest.mark.skipif(os.name == "nt", reason="POSIX owner-only permissions contract")
def test_private_io_keeps_replacement_atomic_and_append_streams_owner_only(tmp_path: Path) -> None:
    target = tmp_path / "private.txt"
    target.write_text("original", encoding="utf-8")

    def fail_before_write(_temporary_path: Path) -> None:
        raise RuntimeError("stop")

    with pytest.raises(RuntimeError, match="stop"):
        atomic_write_private_text(target, "replacement", before_write=fail_before_write)
    assert target.read_text(encoding="utf-8") == "original"

    atomic_write_private_text(target, "replacement")
    with open_private_append_text(target) as handle:
        handle.write("+append")
    assert target.read_text(encoding="utf-8") == "replacement+append"
    assert target.stat().st_mode & 0o777 == 0o600
