"""Terminal reporting of the undo command: refused and failed reverts are explained on stderr."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from folionym.interfaces.cli.undo import run_undo
from folionym.rename_ops import filesystem


def test_undo_refuses_cross_directory_log_entries(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    original = tmp_path / "original"
    renamed = tmp_path / "renamed"
    original.mkdir()
    renamed.mkdir()
    moved = renamed / "document.pdf"
    moved.write_bytes(b"pdf")
    log = tmp_path / "rename.log"
    log.write_text(f"{original / 'document.pdf'}\t{moved}\n", encoding="utf-8")

    run_undo(log, dry_run=False)

    assert moved.exists()
    assert "cross-directory undo denied" in capsys.readouterr().err


def test_undo_preserves_an_occupied_original_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    original = tmp_path / "original.pdf"
    renamed = tmp_path / "renamed.pdf"
    original.write_bytes(b"occupied")
    renamed.write_bytes(b"renamed")
    log = tmp_path / "rename.log"
    log.write_text(f"{original}\t{renamed}\n", encoding="utf-8")

    run_undo(log, dry_run=False)

    assert original.read_bytes() == b"occupied"
    assert renamed.read_bytes() == b"renamed"
    assert "old path already exists" in capsys.readouterr().err


def test_undo_does_not_overwrite_a_destination_created_after_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    original = tmp_path / "original.pdf"
    renamed = tmp_path / "renamed.pdf"
    renamed.write_bytes(b"renamed")
    log = tmp_path / "rename.log"
    log.write_text(f"{original}\t{renamed}\n", encoding="utf-8")

    def collide(
        _source: Path,
        target: Path,
        _identity: os.stat_result,
        *,
        directory_fd: int,
    ) -> os.stat_result | None:
        del directory_fd
        target.write_bytes(b"racer")
        raise FileExistsError(f"Target already exists: {target}")

    monkeypatch.setattr(filesystem, "_try_hard_link_without_overwrite", collide)

    run_undo(log, dry_run=False)

    assert original.read_bytes() == b"racer"
    assert renamed.read_bytes() == b"renamed"
    assert "Error reverting" in capsys.readouterr().err
