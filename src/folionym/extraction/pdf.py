"""Low-level PDF extraction adapters.

Higher-level modules decide when OCR or vision should run; this module handles
PyMuPDF text/metadata access, optional OCR fallback, and first-page rendering.
"""

from __future__ import annotations

import base64
import contextlib
import logging
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..infrastructure.files import private_regular_file_snapshot, read_regular_file_no_follow
from ..infrastructure.tokens import count_tokens
from ..settings.environment import ENV_OCR_LANG
from ..settings.models import (
    DEFAULT_VISION_MAX_DIMENSION_PIXELS,
    DEFAULT_VISION_MAX_ENCODED_BYTES,
    DEFAULT_VISION_MAX_PIXELS,
    DEFAULT_VISION_RENDER_DPI,
)
from .metadata import empty_pdf_metadata, normalize_pdf_metadata
from .models import OcrExtractionRequest

if TYPE_CHECKING:
    import fitz as _fitz_mod

logger = logging.getLogger(__name__)


class NoTextExtractedError(ValueError):
    """A PDF with pages yielded no text and looks image-only."""


# Minimum extracted characters below which we try OCR (image-only PDFs).
MIN_CHARS_BEFORE_OCR = 50

# Default DPI for first-page render when using vision fallback.
VISION_FALLBACK_DPI = DEFAULT_VISION_RENDER_DPI
VISION_MAX_PIXELS = DEFAULT_VISION_MAX_PIXELS
VISION_MAX_DIMENSION_PIXELS = DEFAULT_VISION_MAX_DIMENSION_PIXELS
VISION_MAX_ENCODED_BYTES = DEFAULT_VISION_MAX_ENCODED_BYTES

# Bounds for browser thumbnails of the first page.
THUMBNAIL_MAX_WIDTH = 900
THUMBNAIL_MAX_HEIGHT = 1200
THUMBNAIL_MAX_SCALE = 1.5
THUMBNAIL_MAX_IMAGE_BYTES = 4 * 1024 * 1024


class PageRenderError(Exception):
    """Raised when no first-page thumbnail can be produced for a PDF."""


class PageRenderUnavailableError(PageRenderError):
    """Raised when the optional rasterization dependency is not installed."""


class PageRenderTooLargeError(PageRenderError):
    """Raised when the encoded thumbnail exceeds the image byte limit."""


@dataclass(frozen=True)
class _VisionRenderLimits:
    """Bounds applied before allocating a first-page vision pixmap."""

    max_pixels: int = VISION_MAX_PIXELS
    max_dimension_pixels: int = VISION_MAX_DIMENSION_PIXELS
    max_encoded_bytes: int = VISION_MAX_ENCODED_BYTES


# Default token limit for local LLMs: 32K is more compatible than 128K.
# reserve ~4K tokens for prompt + response.
DEFAULT_MAX_CONTENT_TOKENS = 28_000

# Token-shrink loop constants
_DENSITY_BUFFER_FACTOR = 1.1  # 10% over-estimate when jumping to approximate target length
_SHRINK_FACTOR = 0.95  # Remove ~5% of text per fine-tuning iteration


def _shrink_to_token_limit(text: str, *, max_tokens: int) -> str:
    """
    Shrink text to a token limit. Uses tiktoken if available, else heuristic.
    Optimized to jump close to the target length to avoid multiple expensive encodings.
    """
    count = count_tokens(text)
    if count <= max_tokens:
        return text

    # Approximate target length based on density
    density = len(text) / max(1, count)
    target_char_count = int(max_tokens * density * _DENSITY_BUFFER_FACTOR)
    if target_char_count < len(text):
        text = text[:target_char_count]

    # Keep shrinking bounded; pathological tokenizers should not turn this into
    # an expensive loop.
    _MAX_SHRINK_ITERATIONS = 50
    for _ in range(_MAX_SHRINK_ITERATIONS):
        if count_tokens(text) <= max_tokens:
            break
        new_len = int(len(text) * _SHRINK_FACTOR)
        # Prefer cut at last space to avoid mid-word truncation
        chunk = text[:new_len]
        last_space = chunk.rfind(" ")
        if last_space > len(text) // 2:
            new_len = last_space
        text = text[:new_len]
    return text


def pdf_to_text(
    filepath: str | Path | None,
    *,
    max_tokens: int | None = DEFAULT_MAX_CONTENT_TOKENS,
    max_pages: int = 0,
    read_all_pages: bool = False,
) -> str:
    """
    Extracts text from a PDF via PyMuPDF (fitz). Import is done lazily so that
    core functionality can be tested without optional deps installed.
    """
    if filepath is None:
        return ""
    fitz = _required_fitz_module()
    path = Path(filepath)
    pieces, errors, page_count = _extract_pdf_text_from_document(
        fitz,
        path,
        max_pages=max_pages,
        max_tokens=None if read_all_pages else max_tokens,
    )
    return _finalize_pdf_text(path, pieces, errors, page_count, max_tokens=max_tokens)


def _required_fitz_module() -> Any:
    """Import PyMuPDF or raise an installation error."""
    try:
        import fitz
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyMuPDF is required for PDF extraction. Install with: pip install -e '.[pdf]'") from exc
    return fitz


def _optional_fitz_module() -> Any | None:
    """Import PyMuPDF when available; otherwise return None."""
    try:
        import fitz
    except ImportError:
        return None
    return fitz


def _close_document(doc: Any) -> None:
    """Close a document when it exposes a callable close method."""
    closer = getattr(doc, "close", None)
    if callable(closer):
        closer()


def _open_pdf_for_text(fitz: Any, path: Path) -> Any:
    """Open a PDF for text extraction and normalize expected failures to OSError."""
    try:
        return fitz.open(stream=read_regular_file_no_follow(path), filetype="pdf")
    except (RuntimeError, OSError, ValueError) as exc:
        raise OSError(f"Could not open PDF file {path.name}: {exc}") from exc


def _extract_pdf_text_from_document(
    fitz: Any,
    path: Path,
    *,
    max_pages: int,
    max_tokens: int | None,
) -> tuple[list[str], list[str], int]:
    """Extract page text and errors, returning no text for encrypted PDFs and always closing the document."""
    doc = _open_pdf_for_text(fitz, path)
    page_count = getattr(doc, "page_count", 0) or 0
    if max_pages > 0:
        page_count = min(page_count, max_pages)
    try:
        if getattr(doc, "is_encrypted", False):
            logger.warning("PDF %s is encrypted/password-protected. Skipping text extraction.", path.name)
            return [], [], page_count
        pieces, errors = _extract_pages(doc, path, max_pages=max_pages, max_tokens=max_tokens)
        return pieces, errors, page_count
    finally:
        _close_document(doc)


def _finalize_pdf_text(
    path: Path,
    pieces: list[str],
    errors: list[str],
    page_count: int,
    *,
    max_tokens: int | None,
) -> str:
    """Join extracted pages, enforce the token limit, or handle an empty extraction."""
    content = "\n".join(pieces).strip()
    if content:
        if max_tokens is None or max_tokens <= 0:
            return content
        return _shrink_to_token_limit(content, max_tokens=max_tokens)
    _handle_empty_pdf_text(path, errors, page_count)
    return ""


def _handle_empty_pdf_text(path: Path, errors: list[str], page_count: int) -> None:
    """Raise or log the appropriate outcome for an empty PDF extraction."""
    if errors and page_count > 0:
        raise RuntimeError(
            f"Extraction failed for {path.name}: {len(errors)} error(s) occurred during page processing. "
            f"First error: {errors[0]}"
        )
    if page_count <= 0:
        return
    msg = (
        f"No text extracted from {path.name} ({page_count} page(s)). "
        "File may be encrypted, image-only, or extraction failed for all pages."
    )
    if _looks_like_image_only_pdf(path):
        raise NoTextExtractedError(f"{msg} Consider using --ocr.")
    logger.warning(msg)


def _looks_like_image_only_pdf(path: Path) -> bool:
    """Use file size as a coarse image-only PDF heuristic."""
    try:
        return path.stat().st_size > 1024
    except OSError as exc:
        logger.debug("Could not stat %s for size check: %s", path.name, exc)
        return False


def _vision_render_payload(rendered: tuple[bytes, str] | None) -> dict[str, str] | None:
    """Base64-encode rendered image bytes with their MIME type."""
    if rendered is None:
        return None
    image_bytes, mime_type = rendered
    if not image_bytes:
        return None
    return {
        "image_b64": base64.b64encode(image_bytes).decode("ascii"),
        "mime_type": mime_type,
    }


def _open_pdf_for_vision(fitz: Any, path: Path) -> Any | None:
    """Open a PDF for vision rendering, returning None on expected failures."""
    try:
        return fitz.open(stream=read_regular_file_no_follow(path), filetype="pdf")
    except (RuntimeError, OSError, ValueError) as exc:
        logger.debug("Could not open PDF for vision render %s: %s", path.name, exc)
        return None


def _encode_pixmap_for_vision(pix: Any, *, max_encoded_bytes: int) -> tuple[bytes, str] | None:
    """Encode a pixmap as JPEG when supported, falling back to PNG."""
    encoded: tuple[bytes, str] | None = None
    if hasattr(pix, "tobytes"):
        # fmt: off
        try:
            encoded = (pix.tobytes(output="jpeg", jpg_quality=85), "image/jpeg")
        except (TypeError, ValueError):
            encoded = (pix.tobytes(output="png"), "image/png")
        # fmt: on
    if hasattr(pix, "getImageData"):
        encoded = (pix.getImageData("jpeg"), "image/jpeg")
    elif hasattr(pix, "getPNGData"):
        encoded = (pix.getPNGData(), "image/png")
    if encoded is None or len(encoded[0]) > max_encoded_bytes:
        return None
    return encoded


def _bounded_vision_dpi(
    page: Any,
    *,
    dpi: int,
    max_pixels: int,
    max_dimension_pixels: int,
    max_encoded_bytes: int,
) -> int | None:
    """Choose an integer DPI whose predicted RGB pixmap stays within every allocation bound."""
    rect = getattr(page, "rect", None)
    width_points = float(getattr(rect, "width", 0.0) or 0.0)
    height_points = float(getattr(rect, "height", 0.0) or 0.0)
    if width_points <= 0 or height_points <= 0:
        return max(1, dpi)
    pixel_budget = min(max_pixels, max_encoded_bytes // 3)
    if pixel_budget <= 0:
        return None
    requested_scale = max(1, dpi) / 72.0
    scale_limit = min(
        requested_scale,
        max_dimension_pixels / width_points,
        max_dimension_pixels / height_points,
        math.sqrt(pixel_budget / (width_points * height_points)),
    )
    bounded_dpi = math.floor(scale_limit * 72.0)
    if bounded_dpi < 1:
        return None
    width_pixels = math.ceil(width_points * bounded_dpi / 72.0)
    height_pixels = math.ceil(height_points * bounded_dpi / 72.0)
    if (
        width_pixels * height_pixels > pixel_budget
        or width_pixels > max_dimension_pixels
        or height_pixels > max_dimension_pixels
    ):
        return None
    return bounded_dpi


def _render_first_page_for_vision(
    doc: Any,
    path: Path,
    *,
    dpi: int,
    limits: _VisionRenderLimits | None = None,
) -> tuple[bytes, str] | None:
    """Render and encode the first page of a non-encrypted PDF for vision."""
    if getattr(doc, "is_encrypted", False):
        logger.debug("PDF %s is encrypted; skipping vision render.", path.name)
        return None
    page_count = getattr(doc, "page_count", 0) or 0
    if page_count == 0:
        return None
    page = doc.load_page(0)
    effective_limits = limits or _VisionRenderLimits()
    bounded_dpi = _bounded_vision_dpi(
        page,
        dpi=dpi,
        max_pixels=effective_limits.max_pixels,
        max_dimension_pixels=effective_limits.max_dimension_pixels,
        max_encoded_bytes=effective_limits.max_encoded_bytes,
    )
    if bounded_dpi is None:
        logger.warning("PDF %s page dimensions exceed the configured vision allocation bounds.", path.name)
        return None
    pix = page.get_pixmap(dpi=bounded_dpi, alpha=False)
    width = int(getattr(pix, "width", 0) or 0)
    height = int(getattr(pix, "height", 0) or 0)
    channels = int(getattr(pix, "n", 3) or 3)
    if (
        width
        and height
        and (
            width * height > effective_limits.max_pixels
            or width * height * channels > effective_limits.max_encoded_bytes
        )
    ):
        return None
    return _encode_pixmap_for_vision(pix, max_encoded_bytes=effective_limits.max_encoded_bytes)


def pdf_first_page_to_image_payload(
    filepath: str | Path | None,
    *,
    dpi: int = VISION_FALLBACK_DPI,
    max_pixels: int = VISION_MAX_PIXELS,
    max_dimension_pixels: int = VISION_MAX_DIMENSION_PIXELS,
    max_encoded_bytes: int = VISION_MAX_ENCODED_BYTES,
) -> dict[str, str] | None:
    """Render the first page and preserve the actual MIME type for vision requests."""
    if filepath is None:
        return None
    fitz = _optional_fitz_module()
    if fitz is None:
        return None
    path = Path(filepath)
    doc = _open_pdf_for_vision(fitz, path)
    if doc is None:
        return None
    try:
        try:
            rendered = _render_first_page_for_vision(
                doc,
                path,
                dpi=dpi,
                limits=_VisionRenderLimits(max_pixels, max_dimension_pixels, max_encoded_bytes),
            )
        except (RuntimeError, OSError, ValueError) as exc:
            logger.debug("Vision render failed for %s: %s", path.name, exc)
            return None
        return _vision_render_payload(rendered)
    finally:
        _close_document(doc)


def _ocr_language_code(lang: str) -> str:
    """Map config language (de/en) to Tesseract/OCRmyPDF language code.
    Can be overridden by FOLIONYM_OCR_LANG.
    """
    override = (os.environ.get(ENV_OCR_LANG) or "").strip()
    if override:
        return override
    if (lang or "").strip().lower() == "en":
        return "eng"
    return "deu"


def pdf_to_text_with_ocr(  # noqa: PLR0913 - stable adapter keeps independent extraction controls
    filepath: str | Path | None,
    *,
    max_tokens: int | None = DEFAULT_MAX_CONTENT_TOKENS,
    max_pages: int = 0,
    min_chars_for_ocr: int = MIN_CHARS_BEFORE_OCR,
    language: str = "de",
    read_all_pages: bool = False,
) -> str:
    """
    Extract text from a PDF; if too little text is found and OCRmyPDF is
    available, run OCR first then extract. Requires optional dependency
    ocrmypdf and system Tesseract. Falls back to non-OCR extraction on
    missing dependency or OCR failure.
    """
    if filepath is None:
        return ""
    path = Path(filepath)
    with private_regular_file_snapshot(path, suffix=".pdf") as snapshot:
        text = _initial_text_for_ocr(
            snapshot,
            max_tokens=max_tokens,
            max_pages=max_pages,
            read_all_pages=read_all_pages,
        )
        if not _should_attempt_ocr(snapshot, text, min_chars_for_ocr=min_chars_for_ocr):
            return text
        ocrmypdf = _ocrmypdf_module_or_none()
        if ocrmypdf is None:
            return text
        return _ocr_text_or_original(
            ocrmypdf,
            OcrExtractionRequest(
                path=snapshot,
                original_text=text,
                max_tokens=max_tokens,
                max_pages=max_pages,
                language=language,
                read_all_pages=read_all_pages,
            ),
            source_path=path,
        )


def _initial_text_for_ocr(
    filepath: str | Path | None,
    *,
    max_tokens: int | None,
    max_pages: int,
    read_all_pages: bool,
) -> str:
    """Try ordinary extraction first; return empty text after expected failures so OCR can run."""
    try:
        return pdf_to_text(
            filepath,
            max_tokens=max_tokens,
            max_pages=max_pages,
            read_all_pages=read_all_pages,
        )
    except (RuntimeError, ValueError) as exc:
        # Extraction failed entirely, so proceed to OCR if available.
        logger.info("Text extraction failed for %s, will try OCR: %s", filepath, exc)
        return ""


def _should_attempt_ocr(
    filepath: str | Path | None,
    text: str,
    *,
    min_chars_for_ocr: int,
) -> bool:
    """Return whether a supplied path produced less than the OCR text threshold."""
    return bool(filepath) and len(text.strip()) < min_chars_for_ocr


def _ocrmypdf_module_or_none() -> Any | None:
    """Import OCRmyPDF or warn and return None."""
    try:
        import ocrmypdf
    except ImportError:
        logger.warning(
            "OCR requested but ocrmypdf not installed. Install with: pip install -e '.[ocr]' (and install Tesseract)."
        )
        return None
    return ocrmypdf


def _ocr_text_or_original(
    ocrmypdf: Any,
    request: OcrExtractionRequest,
    *,
    source_path: Path | None = None,
) -> str:
    """Run OCR and return its text, falling back to the original extraction on expected failures."""
    tmp = None
    try:
        tmp = _create_ocr_temp_path()
        _run_ocr_to_temp(ocrmypdf, request.path, tmp, language=request.language)
        text_ocr = _extract_ocr_temp_text(
            tmp,
            source_path or request.path,
            max_tokens=request.max_tokens,
            max_pages=request.max_pages,
            read_all_pages=request.read_all_pages,
        )
        if text_ocr is not None:
            return text_ocr
    except (RuntimeError, OSError, ValueError) as exc:
        logger.warning("OCR failed for %s: %s. Using original extraction.", request.path, exc)
    finally:
        _remove_ocr_temp_path(tmp)
    return request.original_text


def _create_ocr_temp_path() -> Path:
    """Create a temporary PDF path for OCRmyPDF output."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, prefix="folionym_ocr_") as f:
        return Path(f.name).resolve(strict=True)


def _run_ocr_to_temp(ocrmypdf: Any, path: Path, tmp: Path, *, language: str) -> None:
    """Run OCRmyPDF and best-effort restrict its replacement output to mode 0600."""
    ocrmypdf.ocr(
        str(path),
        str(tmp),
        language=_ocr_language_code(language),
    )
    # ocrmypdf typically renames its own temp output into `tmp`, creating a new inode
    # with umask-based permissions. Restore 0600 so the OCR output isn't world-readable.
    with contextlib.suppress(OSError):
        tmp.chmod(0o600)


def _extract_ocr_temp_text(
    tmp: Path,
    source_path: Path,
    *,
    max_tokens: int | None,
    max_pages: int,
    read_all_pages: bool,
) -> str | None:
    """Extract text from OCR output, returning None when it remains empty."""
    text_ocr = pdf_to_text(
        tmp,
        max_tokens=max_tokens,
        max_pages=max_pages,
        read_all_pages=read_all_pages,
    )
    if not text_ocr.strip():
        return None
    logger.info("OCR produced %s chars for %s", len(text_ocr.strip()), source_path.name)
    return text_ocr


def _remove_ocr_temp_path(tmp: Path | None) -> None:
    """Best-effort remove the OCR temporary file."""
    if tmp is not None and tmp.exists():
        with contextlib.suppress(OSError):
            tmp.unlink()


def get_pdf_metadata(filepath: str | Path | None) -> dict[str, object]:
    """
    Read PDF metadata (Title, Author, CreationDate, ModDate) without extracting text.
    Returns dict with keys: title (str), author (str), creation_date (YYYY-MM-DD or None),
    mod_date (YYYY-MM-DD or None). Empty dict on error or missing PyMuPDF.
    """
    result = empty_pdf_metadata()
    if not filepath:
        return result
    fitz = _optional_fitz_module()
    if fitz is None:
        return result
    path = Path(filepath)
    doc = _open_pdf_for_metadata(fitz, path)
    if doc is None:
        return result
    try:
        return normalize_pdf_metadata(doc)
    finally:
        _close_document(doc)


def _open_pdf_for_metadata(fitz: Any, path: Path) -> Any | None:
    """Open a PDF for metadata, returning None and debug-logging expected failures."""
    try:
        return fitz.open(stream=read_regular_file_no_follow(path), filetype="pdf")
    except (RuntimeError, OSError, ValueError) as exc:
        logger.debug("Could not open PDF for metadata %s: %s", path, exc)
        return None


def _extract_pages(
    doc: _fitz_mod.Document,
    path: Path,
    *,
    max_pages: int = 0,
    max_tokens: int | None = None,
) -> tuple[list[str], list[str]]:
    """Extract text from pages. Returns (pieces, errors)."""
    pieces: list[str] = []
    errors: list[str] = []
    accumulated_tokens = 0
    limit = min(doc.page_count, max_pages) if max_pages > 0 else doc.page_count
    for page_number in range(limit):
        try:
            # load_page() is stable across supported PyMuPDF versions.
            page = doc.load_page(page_number)
        except (IndexError, RuntimeError, OSError, ValueError) as exc:
            msg = f"Error accessing page {page_number} in {path.name}: {exc}"
            logger.error(msg)
            errors.append(msg)
            continue

        page_text = ""
        try:
            page_text = (page.get_text("text") or "").strip()
        except (RuntimeError, OSError, ValueError) as exc:
            msg = f"Page {page_number} text extraction failed in {path.name}: {exc}. Use --ocr to try OCR extraction."
            logger.warning(msg)
            errors.append(msg)

        combined = page_text
        if combined:
            token_piece = f"\n{combined}" if pieces else combined
            pieces.append(combined)
            logger.debug(
                "Combined extracted %s characters from page %s of %s",
                len(combined),
                page_number,
                path,
            )
            if max_tokens is not None and max_tokens > 0:
                accumulated_tokens += count_tokens(token_piece)
                if accumulated_tokens >= max_tokens:
                    candidate = "\n".join(pieces).strip()
                    exact_tokens = count_tokens(candidate)
                    if exact_tokens >= max_tokens:
                        pieces[:] = [_shrink_to_token_limit(candidate, max_tokens=max_tokens)]
                        break
                    accumulated_tokens = exact_tokens
        else:
            logger.info("Page %s in %s yields no text.", page_number, path)

    return pieces, errors


def render_first_page_thumbnail(
    path: str | Path,
    *,
    max_width: int = THUMBNAIL_MAX_WIDTH,
    max_height: int = THUMBNAIL_MAX_HEIGHT,
    max_scale: float = THUMBNAIL_MAX_SCALE,
    max_bytes: int = THUMBNAIL_MAX_IMAGE_BYTES,
) -> bytes:
    """Render page one as a PNG whose pixel dimensions are bounded before rasterization.

    Raises ``PageRenderUnavailableError`` without PyMuPDF, ``PageRenderTooLargeError``
    when the PNG exceeds ``max_bytes``, and ``PageRenderError`` for any other failure.
    """
    try:
        import fitz

        data = read_regular_file_no_follow(Path(path))
        with fitz.open(stream=data, filetype="pdf") as document:
            if document.page_count < 1:
                raise PageRenderError("No page preview is available.")
            page = document.load_page(0)
            width, height = float(page.rect.width), float(page.rect.height)
            if not all(math.isfinite(value) and value > 0 for value in (width, height)):
                raise PageRenderError("Invalid page dimensions.")
            scale = min(max_scale, max_width / width, max_height / height)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            data = bytes(pixmap.tobytes("png"))
    except ImportError as exc:
        raise PageRenderUnavailableError("PDF thumbnails require the web extra.") from exc
    except (OSError, RuntimeError, ValueError) as exc:
        raise PageRenderError("No page preview is available.") from exc
    if len(data) > max_bytes:
        raise PageRenderTooLargeError("The page preview exceeds the image limit.")
    return data
