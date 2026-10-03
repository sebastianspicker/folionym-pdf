"""PDF metadata rewriting through optional PyMuPDF access."""

from __future__ import annotations

import contextlib
import logging
import os
import stat
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _cleanup_temp_pdf(temp_pdf: Path | None) -> None:
    """Remove a temporary PDF when a metadata write cannot be completed."""
    if temp_pdf is not None:
        with contextlib.suppress(OSError):
            temp_pdf.unlink()


def _create_pdf_metadata_temp(pdf_path: Path) -> Path:
    """Create a same-directory temporary PDF and close its file descriptor."""
    import tempfile

    fd, temp_path = tempfile.mkstemp(suffix=".pdf", dir=pdf_path.parent)
    temp_pdf = Path(temp_path)
    try:
        os.close(fd)
    except OSError:
        _cleanup_temp_pdf(temp_pdf)
        raise
    return temp_pdf


def _save_pdf_to_temp(doc: Any, temp_pdf: Path, encryption_keep: object | None) -> None:
    """Save metadata to a temporary PDF, retrying old PyMuPDF signatures once."""
    save_options: dict[str, object] = {"incremental": False}
    if encryption_keep is not None:
        save_options["encryption"] = encryption_keep

    last_type_error: TypeError | None = None
    for options in (save_options, {"incremental": False}):
        try:
            doc.save(str(temp_pdf), **options)
            return
        except TypeError as exc:
            # Older PyMuPDF builds may expose incompatible save signatures.
            last_type_error = exc
        except AttributeError, OSError, RuntimeError, ValueError:
            _cleanup_temp_pdf(temp_pdf)
            raise

    _cleanup_temp_pdf(temp_pdf)
    if last_type_error is not None:
        raise last_type_error


def _replace_nonempty_temp_pdf(temp_pdf: Path, pdf_path: Path) -> None:
    """Atomically replace a PDF only after its temporary replacement has data."""
    if temp_pdf.stat().st_size == 0:
        raise OSError(f"Temporary PDF file is empty (possible disk full): {temp_pdf}")
    # mkstemp creates the file as 0600; keep the user's original permission bits.
    os.chmod(temp_pdf, stat.S_IMODE(pdf_path.stat().st_mode))
    # Atomic replace (os.replace is atomic on POSIX, best-effort on Windows).
    os.replace(temp_pdf, pdf_path)


def write_document_metadata(pdf_path: Path, title: str) -> None:
    """Write /Title metadata to PDF (PyMuPDF). Logs a warning if fitz is unavailable or on error.

    Writes to a temporary file first, then atomically replaces the original to
    prevent corruption under concurrent access.
    """
    temp_pdf: Path | None = None
    try:
        import fitz

        doc = fitz.open(pdf_path)
        try:
            doc.set_metadata({"title": title or pdf_path.stem})
            temp_pdf = _create_pdf_metadata_temp(pdf_path)
            encryption_keep = getattr(fitz, "PDF_ENCRYPT_KEEP", None)
            _save_pdf_to_temp(doc, temp_pdf, encryption_keep)
        finally:
            doc.close()
        _replace_nonempty_temp_pdf(temp_pdf, pdf_path)
    except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
        _cleanup_temp_pdf(temp_pdf)
        logger.warning("Could not write PDF metadata for %s: %s", pdf_path, exc)
