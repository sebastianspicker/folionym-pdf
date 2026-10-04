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
    with pytest.raises(OSError, match=r"Source (?:path )?changed"):
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
    monkeypatch.setattr(filesystem, "_try_hard_link_without_overwrite", lambda *_args, **_kwargs: None)

    def fail_copy(*_args: object) -> None:
        raise OSError("forced copy failure")

    monkeypatch.setattr(filesystem, "_copy_fd_to_fd", fail_copy)
    with pytest.raises(OSError, match="forced copy failure"):
        apply_single_rename(source, "invoice", RenameApplyOptions())
    assert source.read_bytes() == b"pdf"
    assert not destination.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX pinned-descriptor fallback contract")
def test_copy_fallback_never_reopens_a_replaced_source_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.pdf"
    destination = tmp_path / "invoice.pdf"
    source.write_bytes(b"reviewed bytes")
    monkeypatch.setattr(filesystem, "_try_hard_link_without_overwrite", lambda *_args, **_kwargs: None)
    original_copy = filesystem._copy_fd_to_fd

    def replace_then_copy(source_fd: int, target_fd: int) -> os.stat_result:
        source.unlink()
        source.write_bytes(b"replacement bytes")
        return original_copy(source_fd, target_fd)

    monkeypatch.setattr(filesystem, "_copy_fd_to_fd", replace_then_copy)

    with pytest.raises(OSError, match=r"Source (?:path )?changed"):
        apply_single_rename(source, "invoice", RenameApplyOptions())

    assert source.read_bytes() == b"replacement bytes"
    assert not destination.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX pinned-directory fallback contract")
def test_copy_fallback_unlinks_only_from_the_pinned_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    selected = tmp_path / "selected"
    displaced = tmp_path / "displaced"
    selected.mkdir()
    source = selected / "source.pdf"
    source.write_bytes(b"reviewed bytes")
    monkeypatch.setattr(filesystem, "_try_hard_link_without_overwrite", lambda *_args, **_kwargs: None)
    original_unlink = filesystem._unlink_copied_source

    def replace_parent_then_unlink(*args: object, **kwargs: object) -> None:
        selected.rename(displaced)
        selected.mkdir()
        (selected / "source.pdf").write_bytes(b"unrelated bytes")
        original_unlink(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(filesystem, "_unlink_copied_source", replace_parent_then_unlink)

    applied, _destination = apply_single_rename(source, "invoice", RenameApplyOptions())

    assert applied
    assert (selected / "source.pdf").read_bytes() == b"unrelated bytes"
    assert not (displaced / "source.pdf").exists()
    assert (displaced / "invoice.pdf").read_bytes() == b"reviewed bytes"


@pytest.mark.skipif(os.name == "nt", reason="POSIX pinned-directory hard-link contract")
def test_hard_link_rename_unlinks_only_from_the_pinned_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = tmp_path / "selected"
    displaced = tmp_path / "displaced"
    selected.mkdir()
    source = selected / "source.pdf"
    source.write_bytes(b"reviewed bytes")
    original_validate = filesystem._validate_link_and_unlink_source

    def replace_parent_then_validate(*args: object, **kwargs: object) -> None:
        selected.rename(displaced)
        selected.mkdir()
        (selected / "source.pdf").write_bytes(b"unrelated bytes")
        original_validate(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(filesystem, "_validate_link_and_unlink_source", replace_parent_then_validate)

    applied, _destination = apply_single_rename(source, "invoice", RenameApplyOptions())

    assert applied
    assert (selected / "source.pdf").read_bytes() == b"unrelated bytes"
    assert not (displaced / "source.pdf").exists()
    assert (displaced / "invoice.pdf").read_bytes() == b"reviewed bytes"


@pytest.mark.skipif(os.name == "nt", reason="POSIX hard-link identity contract")
def test_hard_link_rename_rejects_in_place_source_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.pdf"
    destination = tmp_path / "invoice.pdf"
    source.write_bytes(b"reviewed bytes")
    original_validate = filesystem._validate_link_and_unlink_source

    def modify_then_validate(*args: object, **kwargs: object) -> None:
        source.write_bytes(b"modified bytes")
        original_validate(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(filesystem, "_validate_link_and_unlink_source", modify_then_validate)

    with pytest.raises(OSError, match="Source changed before removal"):
        apply_single_rename(source, "invoice", RenameApplyOptions())

    assert source.read_bytes() == b"modified bytes"
    assert not destination.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX pinned-descriptor fallback contract")
def test_copy_fallback_rejects_in_place_source_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.pdf"
    destination = tmp_path / "invoice.pdf"
    source.write_bytes(b"reviewed bytes")
    monkeypatch.setattr(filesystem, "_try_hard_link_without_overwrite", lambda *_args, **_kwargs: None)
    original_copy = filesystem._copy_fd_to_fd

    def copy_then_modify(source_fd: int, target_fd: int) -> os.stat_result:
        identity = original_copy(source_fd, target_fd)
        source.write_bytes(b"modified bytes")
        return identity

    monkeypatch.setattr(filesystem, "_copy_fd_to_fd", copy_then_modify)

    with pytest.raises(OSError, match="Source changed while copying"):
        apply_single_rename(source, "invoice", RenameApplyOptions())

    assert source.read_bytes() == b"modified bytes"
    assert not destination.exists()


def test_copy_fallback_can_close_windows_source_before_unlink(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    destination = tmp_path / "invoice.pdf"
    source.write_bytes(b"reviewed bytes")
    source_fd = os.open(source, os.O_RDONLY)
    closed = False

    def close_source() -> None:
        nonlocal closed
        os.close(source_fd)
        closed = True

    try:
        filesystem._copy_with_pinned_source(
            source,
            destination,
            source_fd,
            before_unlink=close_source,
            expected_identity=None,
            directory_fd=None,
        )
    finally:
        if not closed:
            os.close(source_fd)

    assert not source.exists()
    assert destination.read_bytes() == b"reviewed bytes"
