"""PDF extraction adapters and configured extraction strategies."""

from .pdf import (
    DEFAULT_MAX_CONTENT_TOKENS,
    PageRenderError,
    PageRenderTooLargeError,
    PageRenderUnavailableError,
    get_pdf_metadata,
    pdf_to_text,
    pdf_to_text_with_ocr,
    render_first_page_thumbnail,
)
from .pipeline import extract_pdf_content

__all__ = [
    "DEFAULT_MAX_CONTENT_TOKENS",
    "PageRenderError",
    "PageRenderTooLargeError",
    "PageRenderUnavailableError",
    "extract_pdf_content",
    "get_pdf_metadata",
    "pdf_to_text",
    "pdf_to_text_with_ocr",
    "render_first_page_thumbnail",
]
