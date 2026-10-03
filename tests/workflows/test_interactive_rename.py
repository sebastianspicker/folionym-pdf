"""Conventional interactive (y/n/e=edit) and manual rename prompts, via the CLI and the public facade."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from folionym.config import build_config
from folionym.interfaces.cli import main as cli_main
from folionym.renamer import rename_pdfs_in_directory

PROPOSED = "20260901-invoice.pdf"
PROMPT = f"Rename 'source.pdf' to '{PROPOSED}'? (y/n/e=edit, default y): "


pytestmark = pytest.mark.usefixtures("isolated_home")


@pytest.fixture
def pdf_dir(tmp_path: Path, make_pdf: Callable[..., Path], invoice_text: str) -> Path:
    directory = tmp_path / "pdfs"
    directory.mkdir()
    make_pdf(directory / "source.pdf", invoice_text)
    return directory


@pytest.fixture
def answers(monkeypatch: pytest.MonkeyPatch) -> Callable[..., list[str]]:
    """Replace input() with scripted replies; an exhausted script raises EOFError. Returns the prompts seen."""

    def install(*replies: str) -> list[str]:
        prompts: list[str] = []
        queue: Iterator[str] = iter(replies)

        def fake_input(prompt: str = "") -> str:
            prompts.append(prompt)
            try:
                return next(queue)
            except StopIteration:
                raise EOFError from None

        monkeypatch.setattr("builtins.input", fake_input)
        return prompts

    return install


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def _facade(directory: Path, **overrides: object) -> None:
    config = build_config({"use_llm": False, "interactive": True, "use_cache": False, **overrides})
    rename_pdfs_in_directory(directory, config=config)


def _cli(directory: Path) -> None:
    cli_main(["--dir", str(directory), "--no-llm", "--no-cache", "--interactive"])


@pytest.fixture(params=["facade", "cli"])
def run_interactive(request: pytest.FixtureRequest) -> Callable[[Path], None]:
    return _facade if request.param == "facade" else _cli


def test_prompt_text_and_yes_renames(
    pdf_dir: Path, answers: Callable[..., list[str]], run_interactive: Callable[[Path], None]
) -> None:
    prompts = answers("y")
    run_interactive(pdf_dir)
    assert prompts == [PROMPT]
    assert _names(pdf_dir) == [PROPOSED]


def test_empty_reply_defaults_to_yes(
    pdf_dir: Path, answers: Callable[..., list[str]], run_interactive: Callable[[Path], None]
) -> None:
    answers("")
    run_interactive(pdf_dir)
    assert _names(pdf_dir) == [PROPOSED]


def test_no_skips_the_file(
    pdf_dir: Path, answers: Callable[..., list[str]], run_interactive: Callable[[Path], None]
) -> None:
    prompts = answers("n")
    run_interactive(pdf_dir)
    assert prompts == [PROMPT]
    assert _names(pdf_dir) == ["source.pdf"]


def test_end_of_input_skips_the_file(
    pdf_dir: Path, answers: Callable[..., list[str]], run_interactive: Callable[[Path], None]
) -> None:
    answers()
    run_interactive(pdf_dir)
    assert _names(pdf_dir) == ["source.pdf"]


def test_edit_renames_to_the_sanitized_edited_name(
    pdf_dir: Path, answers: Callable[..., list[str]], run_interactive: Callable[[Path], None]
) -> None:
    prompts = answers("e", "My Custom: Name?.pdf")
    run_interactive(pdf_dir)
    assert prompts == [PROMPT, "New filename (without path): "]
    assert _names(pdf_dir) == ["My Custom Name.pdf"]


def test_manual_mode_prints_suggestion_and_edit_prompt_offers_the_default(
    pdf_dir: Path, answers: Callable[..., list[str]], capsys: pytest.CaptureFixture[str]
) -> None:
    prompts = answers("e", "")
    cli_main(["--manual", str(pdf_dir / "source.pdf"), "--no-llm", "--no-cache"])
    out = capsys.readouterr().out
    assert f"Suggested: {PROPOSED}\n" in out
    assert "  category: invoice\n" in out
    assert prompts == [PROMPT, f"New filename (without path) [default: {PROPOSED.removesuffix('.pdf')}]: "]
    assert _names(pdf_dir) == [PROPOSED]


def test_manual_mode_through_the_facade_prints_suggestion(
    pdf_dir: Path, answers: Callable[..., list[str]], capsys: pytest.CaptureFixture[str]
) -> None:
    answers("n")
    _facade(pdf_dir, manual_mode=True)
    assert f"Suggested: {PROPOSED}\n" in capsys.readouterr().out
    assert _names(pdf_dir) == ["source.pdf"]


def test_edit_strips_an_uppercase_pdf_suffix(
    pdf_dir: Path, answers: Callable[..., list[str]], run_interactive: Callable[[Path], None]
) -> None:
    answers("e", "My Name.PDF")
    run_interactive(pdf_dir)
    assert _names(pdf_dir) == ["My Name.pdf"]
