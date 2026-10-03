"""PDF metadata normalization keeps a stable shape."""

from __future__ import annotations

import stat
import sys
from collections.abc import Callable
from pathlib import Path

import fitz
import pytest

from folionym.extraction.metadata import normalize_pdf_metadata
from folionym.extraction.writer import write_document_metadata


def test_metadata_normalization_preserves_the_stable_shape() -> None:
    class FakeDocument:
        def __init__(self) -> None:
            self.metadata = {
                "title": "  Invoice  ",
                "author": "  Ada  ",
                "creationDate": "D:20260203120000+01'00'",
                "modDate": "not-a-pdf-date",
            }

    assert normalize_pdf_metadata(FakeDocument()) == {
        "title": "Invoice",
        "author": "Ada",
        "creation_date": "2026-02-03",
        "mod_date": None,
    }


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_write_document_metadata_preserves_file_mode(tmp_path: Path, make_pdf: Callable[..., Path]) -> None:
    pdf = make_pdf(tmp_path / "doc.pdf", "hello")
    pdf.chmod(0o644)

    write_document_metadata(pdf, "New Title")

    assert stat.S_IMODE(pdf.stat().st_mode) == 0o644
    with fitz.open(pdf) as document:
        assert document.metadata["title"] == "New Title"
