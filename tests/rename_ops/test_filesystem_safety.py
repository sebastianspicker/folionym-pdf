"""Small direct contracts for safe local renames: preview, no overwrite, traversal, symlinks, copy failure."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from folionym.rename_ops import RenameApplyOptions, apply_single_rename, filesystem


def test_rename_is_previewable_no_overwrite_and_blocks_traversal(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    occupied = tmp_path / "invoice.pdf"
    source.write_bytes(b"pdf")
    occupied.write_bytes(b"existing")

    preview, candidate = apply_single_rename(source, "invoice", RenameApplyOptions(dry_run=True))
    assert preview and candidate.name == "invoice_1.pdf" and source.exists()

    applied, destination = apply_single_rename(source, "invoice", RenameApplyOptions())
    assert applied and destination == candidate and destination.read_bytes() == b"pdf"
    assert occupied.read_bytes() == b"existing"

    escaped = tmp_path / "again.pdf"
    escaped.write_bytes(b"pdf")
    with pytest.raises(ValueError):
        apply_single_rename(escaped, "../outside", RenameApplyOptions())


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink identity contract")
def test_rename_refuses_source_symlinks_and_preserves_dangling_targets(tmp_path: Path) -> None:
    original = tmp_path / "original.pdf"
    source_link = tmp_path / "source-link.pdf"
    original.write_bytes(b"pdf")
    source_link.symlink_to(original)
    with pytest.raises(OSError, match="Source path changed"):
        apply_single_rename(source_link, "renamed", RenameApplyOptions())
    assert source_link.is_symlink() and original.exists()
    assert not (tmp_path / "renamed.pdf").exists()

    source = tmp_path / "source.pdf"
    dangling_target = tmp_path / "invoice.pdf"
    source.write_bytes(b"pdf")
    dangling_target.symlink_to(tmp_path / "missing.pdf")
    applied, destination = apply_single_rename(source, "invoice", RenameApplyOptions())
    assert applied and destination.name == "invoice_1.pdf"
    assert dangling_target.is_symlink() and destination.read_bytes() == b"pdf"


def test_copy_failure_keeps_source_and_removes_reserved_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.pdf"
    destination = tmp_path / "invoice.pdf"
    source.write_bytes(b"pdf")
    monkeypatch.setattr(filesystem, "_try_hard_link_without_overwrite", lambda *_args: None)

    def fail_copy(*_args: object) -> None:
        raise OSError("forced copy failure")

    monkeypatch.setattr(filesystem, "_copy_file_to_fd", fail_copy)
    with pytest.raises(OSError, match="forced copy failure"):
        apply_single_rename(source, "invoice", RenameApplyOptions())
    assert source.read_bytes() == b"pdf"
    assert not destination.exists()
