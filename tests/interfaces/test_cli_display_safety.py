"""CLI outcome reporting treats logged paths as inert text."""

from __future__ import annotations

from pathlib import Path

from folionym.application.undo import UndoOutcome, UndoOutcomeKind
from folionym.interfaces.cli.undo import _report


def test_undo_report_escapes_terminal_controls(capsys) -> None:
    outcome = UndoOutcome(
        UndoOutcomeKind.REVERTED,
        Path("old.pdf"),
        Path("bad\x1b[2J.pdf"),
    )

    _report(outcome)

    captured = capsys.readouterr().out
    assert captured == "Reverted: bad\\x1b[2J.pdf -> old.pdf\n"
    assert "\x1b" not in captured
