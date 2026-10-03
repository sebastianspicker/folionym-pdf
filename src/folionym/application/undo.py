"""Undo use case: revert renames recorded in a rename log, newest first."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from ..infrastructure.files import is_path_within
from ..rename_ops.execution import apply_exact_rename
from .rename_log import read_rename_log_pairs


class UndoOutcomeKind(StrEnum):
    """Result category for one rename log entry."""

    REVERTED = "reverted"
    WOULD_REVERT = "would_revert"
    SKIPPED = "skipped"
    ERROR = "error"


class UndoSkipReason(StrEnum):
    """Label for why a rename log entry was not undone."""

    PATH_TRAVERSAL = "path traversal detected"
    CROSS_DIRECTORY = "cross-directory undo denied"
    NEW_PATH_MISSING = "new path missing"
    OLD_PATH_EXISTS = "old path already exists"


@dataclass(frozen=True)
class UndoOutcome:
    """Outcome of undoing one logged rename; ``reason`` is the skip label or error text."""

    kind: UndoOutcomeKind
    old: Path
    new: Path
    reason: str = ""
    # Path named in a skip message (the offending candidate for traversal skips).
    subject: Path | None = None


def _same_parent(old_p: Path, new_p: Path) -> bool | None:
    """Compare parent defensively because path resolution can fail."""
    try:
        return old_p.parent.resolve() == new_p.parent.resolve()
    except OSError:
        return None


def _skip_reason(old_p: Path, new_p: Path, trusted_root: Path) -> tuple[UndoSkipReason, Path] | None:
    """Return a skip label and subject path, or None when the pair may be undone."""
    for candidate in (old_p, new_p):
        if not is_path_within(candidate, trusted_root):
            return UndoSkipReason.PATH_TRAVERSAL, candidate
    same_parent = _same_parent(old_p, new_p)
    if same_parent is None:
        return UndoSkipReason.PATH_TRAVERSAL, new_p
    if not same_parent:
        return UndoSkipReason.CROSS_DIRECTORY, new_p
    if not new_p.exists():
        return UndoSkipReason.NEW_PATH_MISSING, new_p
    if old_p.exists() and old_p.resolve() != new_p.resolve():
        return UndoSkipReason.OLD_PATH_EXISTS, old_p
    return None


def _undo_pair(old_path: str, new_path: str, *, trusted_root: Path, dry_run: bool) -> UndoOutcome:
    """Validate one logged rename pair, then preview or perform its reversal."""
    old_p, new_p = Path(old_path), Path(new_path)
    skip = _skip_reason(old_p, new_p, trusted_root)
    if skip is not None:
        return UndoOutcome(UndoOutcomeKind.SKIPPED, old_p, new_p, skip[0], skip[1])
    if dry_run:
        return UndoOutcome(UndoOutcomeKind.WOULD_REVERT, old_p, new_p)
    try:
        apply_exact_rename(new_p, old_p)
    except OSError as exc:
        return UndoOutcome(UndoOutcomeKind.ERROR, old_p, new_p, str(exc))
    return UndoOutcome(UndoOutcomeKind.REVERTED, old_p, new_p)


def undo_rename_log(log_path: Path, *, dry_run: bool) -> Iterator[UndoOutcome]:
    """Revert (or preview reverting) every entry of an existing rename log file, LIFO.

    Outcomes are yielded as each entry is processed so callers can report progress.
    The log's directory is the trusted root: both paths of every entry must resolve
    within that tree. Relative entries resolve against the current directory. Nothing
    is yielded when the log holds no valid entries.
    """
    trusted_root = log_path.resolve().parent
    for old_path, new_path in read_rename_log_pairs(log_path):
        yield _undo_pair(old_path, new_path, trusted_root=trusted_root, dry_run=dry_run)
