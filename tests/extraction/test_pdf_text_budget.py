"""Text extraction reads only the pages its token and page budget needs, preserving order and page errors."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from folionym.extraction import pdf
from folionym.extraction.pipeline import effective_max_tokens
from folionym.settings.models import ExtractionConfig, RenamerConfig

PagesFactory = Callable[[list[str | BaseException]], Any]


def test_budgeted_extraction_stops_after_satisfying_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_pdf_document: PagesFactory, fake_fitz: Callable[[Any], Any]
) -> None:
    document = fake_fitz(fake_pdf_document([f"page-{number:04d} " * 80 for number in range(1000)]))
    monkeypatch.setattr(pdf, "count_tokens", len)

    content = pdf.pdf_to_text(tmp_path / "long.pdf", max_tokens=100)

    assert document.loads == [0]
    assert len(content) <= 100
    assert content.startswith("page-0000")
    assert document.closed


def test_full_extraction_reads_all_pages_in_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_pdf_document: PagesFactory, fake_fitz: Callable[[Any], Any]
) -> None:
    document = fake_fitz(fake_pdf_document(["first", "second", "third"]))
    monkeypatch.setattr(pdf, "count_tokens", len)

    assert pdf.pdf_to_text(tmp_path / "full.pdf", max_tokens=None) == "first\nsecond\nthird"
    assert document.loads == [0, 1, 2]


def test_budgeted_extraction_preserves_page_errors_and_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_pdf_document: PagesFactory, fake_fitz: Callable[[Any], Any]
) -> None:
    document = fake_fitz(fake_pdf_document([RuntimeError("broken"), "second-page", "third-page"]))
    monkeypatch.setattr(pdf, "count_tokens", len)

    assert pdf.pdf_to_text(tmp_path / "partial.pdf", max_tokens=11) == "second-page"
    assert document.loads == [0, 1]


def test_sparse_extraction_does_not_retokenize_the_growing_joined_prefix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_pdf_document: PagesFactory, fake_fitz: Callable[[Any], Any]
) -> None:
    document = fake_fitz(fake_pdf_document(["x"] * 1000))
    tokenized_lengths: list[int] = []

    def count(text: str) -> int:
        tokenized_lengths.append(len(text))
        return len(text)

    monkeypatch.setattr(pdf, "count_tokens", count)

    assert len(pdf.pdf_to_text(tmp_path / "sparse.pdf", max_tokens=10_000)) == 1999
    assert document.loads == list(range(1000))
    assert max(tokenized_lengths[:-1]) <= 2
    assert tokenized_lengths[-1] == 1999


def test_compatibility_extraction_reads_all_pages_before_final_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_pdf_document: PagesFactory, fake_fitz: Callable[[Any], Any]
) -> None:
    config = RenamerConfig(extraction=ExtractionConfig(full_text_extraction=True))
    document = fake_fitz(fake_pdf_document(["first-page", "second-page", "third-page"]))
    monkeypatch.setattr(pdf, "count_tokens", len)

    content = pdf.pdf_to_text(tmp_path / "compat.pdf", max_tokens=11, read_all_pages=True)

    assert effective_max_tokens(config) == pdf.DEFAULT_MAX_CONTENT_TOKENS
    assert document.loads == [0, 1, 2]
    assert len(content) <= 11
    assert content.startswith("first-page")


def test_text_adapter_honors_page_and_token_limits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_pdf_document: PagesFactory, fake_fitz: Callable[[Any], Any]
) -> None:
    document = fake_fitz(fake_pdf_document(["first page", "second page"]))

    assert pdf.pdf_to_text(tmp_path / "source.pdf", max_pages=1) == "first page"
    assert document.closed

    # The token budget is applied through the real text entry point.
    monkeypatch.setattr(pdf, "count_tokens", len)
    assert len(pdf.pdf_to_text(tmp_path / "source.pdf", max_tokens=8, read_all_pages=True)) <= 8
