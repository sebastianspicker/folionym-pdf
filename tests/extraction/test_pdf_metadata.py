"""PDF metadata normalization keeps a stable shape."""

from __future__ import annotations

import stat
import sys
from collections.abc import Callable
from pathlib import Path

import fitz
import pytest

from folionym.extraction import writer
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


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink and permission contract")
def test_metadata_temp_substitution_cannot_chmod_or_remove_the_replacement(
    tmp_path: Path, make_pdf: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = make_pdf(tmp_path / "doc.pdf", "hello")
    pdf.chmod(0o644)
    original_pdf = pdf.read_bytes()
    victim = tmp_path / "private.txt"
    victim.write_bytes(b"private")
    victim.chmod(0o600)
    original_save = writer._save_pdf_to_temp

    def substitute_after_save(doc, temp_pdf, encryption_keep) -> None:
        original_save(doc, temp_pdf, encryption_keep)
        temp_pdf.path.unlink()
        temp_pdf.path.symlink_to(victim)

    monkeypatch.setattr(writer, "_save_pdf_to_temp", substitute_after_save)

    write_document_metadata(pdf, "New Title")

    assert pdf.read_bytes() == original_pdf
    assert victim.read_bytes() == b"private"
    assert stat.S_IMODE(victim.stat().st_mode) == 0o600
    assert any(path.is_symlink() for path in tmp_path.iterdir() if path.suffix == ".pdf" and path != pdf)
