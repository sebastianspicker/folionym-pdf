"""CLI for reverting renames from a rename log (--rename-log). Entry point: folionym-undo.

The log format and the undo use case live in ``folionym.application``; this module owns
argument parsing, exit codes, and message output.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from ...application.undo import UndoOutcome, UndoOutcomeKind, UndoSkipReason, undo_rename_log
from ...infrastructure.display import escape_terminal_text


def _report(outcome: UndoOutcome) -> None:
    """Print one undo outcome using the established stdout/stderr messages."""
    old = escape_terminal_text(outcome.old)
    new = escape_terminal_text(outcome.new)
    reason = escape_terminal_text(outcome.reason)
    subject = escape_terminal_text(outcome.subject)
    match outcome.kind:
        case UndoOutcomeKind.REVERTED:
            print(f"Reverted: {new} -> {old}")
        case UndoOutcomeKind.WOULD_REVERT:
            print(f"Would revert: {new} -> {old}")
        case UndoOutcomeKind.ERROR:
            print(f"Error reverting {new}: {reason}", file=sys.stderr)
        case UndoOutcomeKind.SKIPPED:
            if outcome.reason == UndoSkipReason.CROSS_DIRECTORY:
                print(f"Skip ({reason}): {new} -> {old}", file=sys.stderr)
            else:
                print(f"Skip ({reason}): {subject}", file=sys.stderr)


def run_undo(log_path: Path, dry_run: bool) -> int:
    """Read rename log and revert renames (LIFO); return how many entries failed with an error."""
    if not log_path.is_file():
        print(
            f"Error: rename log path is not a file (e.g. directory): {escape_terminal_text(log_path)}",
            file=sys.stderr,
        )
        return 1
    counts = Counter(UndoOutcomeKind(outcome.kind) for outcome in _reported(undo_rename_log(log_path, dry_run=dry_run)))
    if not counts:
        print("No entries in rename log.", file=sys.stderr)
        return 0
    done = counts[UndoOutcomeKind.WOULD_REVERT] if dry_run else counts[UndoOutcomeKind.REVERTED]
    errors = counts[UndoOutcomeKind.ERROR]
    print(
        f"{'Would revert' if dry_run else 'Reverted'} {done}, skipped {counts[UndoOutcomeKind.SKIPPED]}, "
        f"{errors} error{'' if errors == 1 else 's'}.",
        file=sys.stderr,
    )
    return errors


def _reported(outcomes: Iterator[UndoOutcome]) -> Iterator[UndoOutcome]:
    """Print each outcome as it happens and pass it on for counting."""
    for outcome in outcomes:
        _report(outcome)
        yield outcome


def main(argv: list[str] | None = None) -> None:
    """Parse command-line input and hand off to the command lifecycle."""
    ap = argparse.ArgumentParser(
        prog="folionym-undo",
        description="Revert renames using a rename log file (produced by --rename-log).",
    )
    ap.add_argument(
        "--rename-log",
        "-l",
        required=True,
        metavar="FILE",
        help="Path to the rename log (tab-separated old/new paths, one per line).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be reverted without making changes.",
    )
    args = ap.parse_args(argv)
    log_path = Path(args.rename_log)
    if not log_path.exists():
        print(f"Error: log file not found: {escape_terminal_text(log_path)}", file=sys.stderr)
        sys.exit(1)
    if not log_path.is_file():
        print(f"Error: log path is not a file: {escape_terminal_text(log_path)}", file=sys.stderr)
        sys.exit(1)
    if run_undo(log_path, args.dry_run):
        sys.exit(1)
