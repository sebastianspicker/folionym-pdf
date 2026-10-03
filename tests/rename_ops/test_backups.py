"""Backups taken by the public rename entry point keep occupied names, private bytes, and clean up failures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from folionym.rename_ops import RenameApplyOptions, apply_single_rename, backups


@pytest.mark.skipif(os.name == "nt", reason="POSIX private backup directory contract")
def test_backups_keep_occupied_names_private_bytes_and_clean_failed_copies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.pdf"
    backup_dir = tmp_path / "backups"
    source.write_bytes(b"exact original bytes")
    backup_dir.mkdir(mode=0o700)
    occupied = backup_dir / source.name
    occupied.write_bytes(b"occupied bytes")

    applied, _target = apply_single_rename(source, "renamed", RenameApplyOptions(backup_dir=backup_dir))
    created = backup_dir / "source_1.pdf"
    assert applied and not source.exists()
    assert occupied.read_bytes() == b"occupied bytes"
    assert created.read_bytes() == b"exact original bytes"
    assert (created.stat().st_mode & 0o777) == 0o600

    second = tmp_path / "second.pdf"
    second.write_bytes(b"second")
    linked_dir = tmp_path / "linked-backups"
    linked_dir.symlink_to(backup_dir, target_is_directory=True)
    with pytest.raises(OSError):
        apply_single_rename(second, "second-renamed", RenameApplyOptions(backup_dir=linked_dir))
    assert second.read_bytes() == b"second"

    def fail_copy(*_args: object) -> None:
        raise OSError("forced backup copy failure")

    monkeypatch.setattr(backups, "_copy_fd_to_fd", fail_copy)
    with pytest.raises(OSError, match="forced backup copy failure"):
        apply_single_rename(second, "second-renamed", RenameApplyOptions(backup_dir=tmp_path / "failed-backups"))
    assert not (tmp_path / "failed-backups" / second.name).exists()
    assert second.read_bytes() == b"second"
