"""Descriptor-based source reads reject symbolic-link substitution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from folionym.infrastructure.files import private_regular_file_snapshot, read_regular_file_no_follow


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="requires no-follow path opens")
def test_verified_read_rejects_final_and_ancestor_symlinks(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    private_pdf = outside / "private.pdf"
    private_pdf.write_bytes(b"private")
    final_link = tmp_path / "linked.pdf"
    final_link.symlink_to(private_pdf)
    linked_directory = tmp_path / "linked-directory"
    linked_directory.symlink_to(outside, target_is_directory=True)

    with pytest.raises(OSError, match="symbolic links"):
        read_regular_file_no_follow(final_link)
    with pytest.raises(OSError, match="symbolic links"):
        read_regular_file_no_follow(linked_directory / "private.pdf")

    assert read_regular_file_no_follow(private_pdf) == b"private"

    with private_regular_file_snapshot(private_pdf, suffix=".pdf") as snapshot:
        assert read_regular_file_no_follow(snapshot) == b"private"
