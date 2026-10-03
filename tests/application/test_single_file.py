"""Immediate single-file rename: unique-available target, skipped blank PDFs, and reported errors."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from folionym.application.single_file import rename_single_file
from folionym.settings.resolution import build_config


def test_rename_single_file_renames_with_a_unique_available_name(
    tmp_path: Path, make_pdf: Callable[..., Path], invoice_text: str
) -> None:
    source = tmp_path / "scan.pdf"
    make_pdf(source, invoice_text)

    result = rename_single_file(source, build_config({"use_llm": False}))

    assert result.success and result.error is None
    assert result.base == "20260901-invoice"
    assert result.target == tmp_path / "20260901-invoice.pdf"
    assert result.target.exists() and not source.exists()


def test_rename_single_file_skips_when_no_content(tmp_path: Path, make_pdf: Callable[..., Path]) -> None:
    source = tmp_path / "blank.pdf"
    make_pdf(source)

    result = rename_single_file(source, build_config({"use_llm": False}))

    assert result.base is None and result.error is None and not result.success
    assert source.exists()


def test_rename_single_file_reports_errors_without_touching_the_source(tmp_path: Path) -> None:
    source = tmp_path / "missing.pdf"

    result = rename_single_file(source, build_config({"use_llm": False}))

    assert not result.success
    assert list(tmp_path.iterdir()) == []
