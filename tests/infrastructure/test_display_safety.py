"""Untrusted path text remains inert at terminal presentation boundaries."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from folionym.infrastructure.display import escape_terminal_text
from folionym.infrastructure.logging import PlainLogFormatter
from folionym.interfaces.cli import terminal


def test_terminal_escape_preserves_unicode_and_exposes_controls() -> None:
    rendered = escape_terminal_text("Rechnung-📄\x1b[2J\n\u202ereversed")

    assert rendered == "Rechnung-📄\\x1b[2J\\n\\u202ereversed"
    assert "\x1b" not in rendered
    assert "\u202e" not in rendered


def test_plain_logs_escape_controls_after_formatting() -> None:
    record = logging.LogRecord("test", logging.WARNING, __file__, 1, "PDF %s", ("bad\x1b[2J.pdf",), None)

    rendered = PlainLogFormatter("%(levelname)s: %(message)s").format(record)

    assert rendered == "WARNING: PDF bad\\x1b[2J.pdf"
    assert "\x1b" not in rendered


def test_cli_confirmation_prompt_never_emits_raw_filename_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts: list[str] = []

    def answer(prompt: str) -> str:
        prompts.append(prompt)
        return "n"

    monkeypatch.setattr("builtins.input", answer)
    source = tmp_path / "bad\x1b[2J.pdf"

    result = terminal._interactive_rename_prompt(source, source.with_name("safe.pdf"), "safe")

    assert result == ("n", "safe")
    assert len(prompts) == 1
    assert "\x1b" not in prompts[0]
    assert "bad\\x1b[2J.pdf" in prompts[0]
