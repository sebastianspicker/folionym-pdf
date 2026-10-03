"""Application-level undo outcomes read from a rename log, using real files."""

from __future__ import annotations

from pathlib import Path

from folionym.application.rename_log import append_rename_log_entry
from folionym.application.undo import UndoOutcomeKind, undo_rename_log


def _log(tmp_path: Path, *pairs: tuple[Path, Path]) -> Path:
    log = tmp_path / "rename.log"
    for old, new in pairs:
        append_rename_log_entry(log, old, new)
    return log


def test_undo_reverts_entries_newest_first(tmp_path: Path) -> None:
    first_old, first_new = tmp_path / "a.pdf", tmp_path / "b.pdf"
    second_old, second_new = tmp_path / "b.pdf", tmp_path / "c.pdf"
    second_new.write_bytes(b"data")
    log = _log(tmp_path, (first_old, first_new), (second_old, second_new))

    outcomes = list(undo_rename_log(log, dry_run=False))

    assert [o.kind for o in outcomes] == [UndoOutcomeKind.REVERTED, UndoOutcomeKind.REVERTED]
    assert [o.new for o in outcomes] == [second_new, first_new]
    assert first_old.read_bytes() == b"data"
    assert not second_new.exists()


def test_undo_dry_run_changes_nothing(tmp_path: Path) -> None:
    old, new = tmp_path / "old.pdf", tmp_path / "new.pdf"
    new.write_bytes(b"data")
    outcomes = list(undo_rename_log(_log(tmp_path, (old, new)), dry_run=True))
    assert [(o.kind, o.old, o.new) for o in outcomes] == [(UndoOutcomeKind.WOULD_REVERT, old, new)]
    assert new.exists() and not old.exists()


def test_undo_empty_log_has_no_outcomes(tmp_path: Path) -> None:
    log = tmp_path / "rename.log"
    log.write_text("\nnot-a-pair\n", encoding="utf-8")
    assert list(undo_rename_log(log, dry_run=False)) == []


def test_undo_skips_missing_new_path(tmp_path: Path) -> None:
    old, new = tmp_path / "old.pdf", tmp_path / "new.pdf"
    (outcome,) = undo_rename_log(_log(tmp_path, (old, new)), dry_run=False)
    assert (outcome.kind, outcome.reason, outcome.subject) == (UndoOutcomeKind.SKIPPED, "new path missing", new)


def test_undo_skips_occupied_old_path(tmp_path: Path) -> None:
    old, new = tmp_path / "old.pdf", tmp_path / "new.pdf"
    old.write_bytes(b"occupied")
    new.write_bytes(b"renamed")
    (outcome,) = undo_rename_log(_log(tmp_path, (old, new)), dry_run=False)
    assert (outcome.kind, outcome.reason, outcome.subject) == (UndoOutcomeKind.SKIPPED, "old path already exists", old)
    assert old.read_bytes() == b"occupied" and new.read_bytes() == b"renamed"


def test_undo_skips_cross_directory_entries(tmp_path: Path) -> None:
    (tmp_path / "other").mkdir()
    old, new = tmp_path / "old.pdf", tmp_path / "other" / "new.pdf"
    new.write_bytes(b"data")
    (outcome,) = undo_rename_log(_log(tmp_path, (old, new)), dry_run=False)
    assert (outcome.kind, outcome.reason) == (UndoOutcomeKind.SKIPPED, "cross-directory undo denied")
    assert new.exists()


def test_undo_skips_paths_outside_the_log_directory(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    old, new = tmp_path / "old.pdf", tmp_path / "new.pdf"
    new.write_bytes(b"data")
    log = logs / "rename.log"
    append_rename_log_entry(log, old, new)
    (outcome,) = undo_rename_log(log, dry_run=False)
    assert (outcome.kind, outcome.reason) == (UndoOutcomeKind.SKIPPED, "path traversal detected")
    assert outcome.subject == old and new.exists()
