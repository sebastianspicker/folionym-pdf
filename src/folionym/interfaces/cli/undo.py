"""CLI for reverting renames from a rename log (--rename-log). Entry point: folionym-undo.

The log format and the undo use case live in ``folionym.application``; this module owns
argument parsing, exit codes, and message output.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ...application.undo import UndoOutcome, UndoOutcomeKind, UndoSkipReason, undo_rename_log


def _report(outcome: UndoOutcome) -> None:
    """Print one undo outcome using the established stdout/stderr messages."""
    match outcome.kind:
        case UndoOutcomeKind.REVERTED:
            print(f"Reverted: {outcome.new} -> {outcome.old}")
        case UndoOutcomeKind.WOULD_REVERT:
            print(f"Would revert: {outcome.new} -> {outcome.old}")
        case UndoOutcomeKind.ERROR:
            print(f"Error reverting {outcome.new}: {outcome.reason}", file=sys.stderr)
        case UndoOutcomeKind.SKIPPED:
            if outcome.reason == UndoSkipReason.CROSS_DIRECTORY:
                print(f"Skip ({outcome.reason}): {outcome.new} -> {outcome.old}", file=sys.stderr)
            else:
                print(f"Skip ({outcome.reason}): {outcome.subject}", file=sys.stderr)


def run_undo(log_path: Path, dry_run: bool) -> None:
    """Read rename log and revert renames (LIFO). Caller must ensure log_path.exists()."""
    if not log_path.is_file():
        print(
            f"Error: rename log path is not a file (e.g. directory): {log_path}",
            file=sys.stderr,
        )
        return
    reported = 0
    for outcome in undo_rename_log(log_path, dry_run=dry_run):
        _report(outcome)
        reported += 1
    if not reported:
        print("No entries in rename log.", file=sys.stderr)


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
        print(f"Error: log file not found: {log_path}", file=sys.stderr)
        sys.exit(1)
    if not log_path.is_file():
        print(f"Error: log path is not a file: {log_path}", file=sys.stderr)
        sys.exit(1)
    run_undo(log_path, args.dry_run)
