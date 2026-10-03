"""First-page thumbnails are bounded before the native render."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from folionym.extraction import render_first_page_thumbnail
from folionym.extraction.pdf import THUMBNAIL_MAX_HEIGHT, THUMBNAIL_MAX_WIDTH


def test_tall_thumbnail_is_bounded_before_native_render(tmp_path: Path, make_pdf: Callable[..., Path]) -> None:
    import fitz

    source = make_pdf(tmp_path / "tall.pdf", width=300, height=10000)
    data = render_first_page_thumbnail(source)
    pixels = fitz.Pixmap(data)
    assert pixels.width <= THUMBNAIL_MAX_WIDTH and pixels.height <= THUMBNAIL_MAX_HEIGHT
