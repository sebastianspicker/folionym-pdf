"""PDF metadata rewriting through optional PyMuPDF access."""

from __future__ import annotations

import contextlib
import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..infrastructure.files import open_regular_file_no_follow, read_regular_file_no_follow

logger = logging.getLogger(__name__)


@dataclass
class _MetadataTemp:
    """A same-directory temporary PDF whose descriptor remains authoritative."""

    path: Path
    fd: int
    identity: os.stat_result


def _path_matches_temp(temp_pdf: _MetadataTemp) -> bool:
    """Return whether the temporary pathname still names the reserved inode."""
    try:
        current = temp_pdf.path.lstat()
    except OSError:
        return False
    return (
        not stat.S_ISLNK(current.st_mode)
        and current.st_dev == temp_pdf.identity.st_dev
        and current.st_ino == temp_pdf.identity.st_ino
    )


def _cleanup_temp_pdf(temp_pdf: _MetadataTemp | None) -> None:
    """Close a metadata temp and unlink only the unchanged reservation."""
    if temp_pdf is None:
        return
    with contextlib.suppress(OSError):
        os.close(temp_pdf.fd)
    if _path_matches_temp(temp_pdf):
        with contextlib.suppress(OSError):
            temp_pdf.path.unlink()


def _create_pdf_metadata_temp(pdf_path: Path) -> _MetadataTemp:
    """Create a same-directory temporary PDF and retain its descriptor."""
    import tempfile

    fd, temp_path = tempfile.mkstemp(suffix=".pdf", dir=pdf_path.parent)
    try:
        return _MetadataTemp(Path(temp_path), fd, os.fstat(fd))
    except OSError:
        os.close(fd)
        with contextlib.suppress(OSError):
            Path(temp_path).unlink()
        raise


def _write_all(fd: int, data: bytes) -> None:
    """Replace descriptor contents with all supplied bytes."""
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        view = view[written:]
    os.fsync(fd)


def _save_pdf_to_temp(doc: Any, temp_pdf: _MetadataTemp, encryption_keep: object | None) -> None:
    """Serialize metadata and write it through the retained temporary descriptor."""
    save_options: dict[str, object] = {"incremental": False}
    if encryption_keep is not None:
        save_options["encryption"] = encryption_keep

    last_type_error: TypeError | None = None
    for options in (save_options, {"incremental": False}):
        try:
            serializer = getattr(doc, "tobytes", None) or getattr(doc, "write", None)
            if serializer is None:
                raise AttributeError("PyMuPDF document does not expose a byte serializer")
            serialized = serializer(**options)
            if not isinstance(serialized, bytes):
                serialized = bytes(serialized)
            _write_all(temp_pdf.fd, serialized)
            return
        except TypeError as exc:
            # Older PyMuPDF builds may expose incompatible save signatures.
            last_type_error = exc
        except AttributeError, OSError, RuntimeError, ValueError:
            raise

    if last_type_error is not None:
        raise last_type_error


def _replace_nonempty_temp_pdf(temp_pdf: _MetadataTemp, pdf_path: Path, source_mode: int) -> None:
    """Atomically replace a PDF only after its temporary replacement has data."""
    if os.fstat(temp_pdf.fd).st_size == 0:
        raise OSError(f"Temporary PDF file is empty (possible disk full): {temp_pdf.path}")
    if not _path_matches_temp(temp_pdf):
        raise OSError(f"Temporary PDF path changed before publication: {temp_pdf.path}")
    if os.name != "nt":
        os.fchmod(temp_pdf.fd, stat.S_IMODE(source_mode))
    else:
        os.chmod(temp_pdf.path, stat.S_IMODE(source_mode), follow_symlinks=False)
    # Atomic replace (os.replace is atomic on POSIX, best-effort on Windows).
    if os.name == "nt":
        os.close(temp_pdf.fd)
        temp_pdf.fd = -1
    os.replace(temp_pdf.path, pdf_path)
    if temp_pdf.fd >= 0:
        os.close(temp_pdf.fd)
        temp_pdf.fd = -1


def write_document_metadata(pdf_path: Path, title: str) -> None:
    """Write /Title metadata to PDF (PyMuPDF). Logs a warning if fitz is unavailable or on error.

    Writes to a temporary file first, then atomically replaces the original to
    prevent corruption under concurrent access.
    """
    temp_pdf: _MetadataTemp | None = None
    try:
        import fitz

        source_fd = open_regular_file_no_follow(pdf_path)
        try:
            source_mode = os.fstat(source_fd).st_mode
        finally:
            os.close(source_fd)
        doc = fitz.open(stream=read_regular_file_no_follow(pdf_path), filetype="pdf")
        try:
            doc.set_metadata({"title": title or pdf_path.stem})
            temp_pdf = _create_pdf_metadata_temp(pdf_path)
            encryption_keep = getattr(fitz, "PDF_ENCRYPT_KEEP", None)
            _save_pdf_to_temp(doc, temp_pdf, encryption_keep)
        finally:
            doc.close()
        _replace_nonempty_temp_pdf(temp_pdf, pdf_path, source_mode)
        temp_pdf = None
    except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
        _cleanup_temp_pdf(temp_pdf)
        logger.warning("Could not write PDF metadata for %s: %s", pdf_path, exc)
