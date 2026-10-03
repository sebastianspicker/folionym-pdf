"""First-page vision rendering is bounded before pixmap allocation and rejects oversized pages or encodings."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from folionym.extraction.pdf import pdf_first_page_to_image_payload


class _VisionPixmap:
    n = 3

    def __init__(self, width: int, height: int, encoded: bytes = b"jpeg") -> None:
        self.width = width
        self.height = height
        self.encoded = encoded

    def tobytes(self, **_kwargs: object) -> bytes:
        return self.encoded


class _VisionPage:
    def __init__(self, width_points: float, height_points: float, encoded: bytes = b"jpeg") -> None:
        self.rect = SimpleNamespace(width=width_points, height=height_points)
        self.requested_dpi: int | None = None
        self.encoded = encoded

    def get_pixmap(self, *, dpi: int, alpha: bool) -> _VisionPixmap:
        assert alpha is False
        self.requested_dpi = dpi
        return _VisionPixmap(
            max(1, int(self.rect.width * dpi / 72)),
            max(1, int(self.rect.height * dpi / 72)),
            self.encoded,
        )


def _document(page: _VisionPage) -> SimpleNamespace:
    return SimpleNamespace(is_encrypted=False, page_count=1, load_page=lambda _number: page)


def test_vision_render_reduces_tall_page_before_pixmap_allocation(
    tmp_path: Path, fake_fitz: Callable[[Any], Any]
) -> None:
    page = _VisionPage(612, 10_000)
    fake_fitz(_document(page))

    payload = pdf_first_page_to_image_payload(
        tmp_path / "tall.pdf", dpi=300, max_pixels=1_000_000, max_dimension_pixels=2048, max_encoded_bytes=4_000_000
    )

    assert payload is not None
    assert page.requested_dpi is not None and page.requested_dpi < 300
    assert int(page.rect.height * page.requested_dpi / 72) <= 2048


def test_vision_render_rejects_huge_page_and_oversized_encoding(
    tmp_path: Path, fake_fitz: Callable[[Any], Any]
) -> None:
    huge_page = _VisionPage(612, 1_000_000)
    fake_fitz(_document(huge_page))
    assert (
        pdf_first_page_to_image_payload(
            tmp_path / "huge.pdf", dpi=300, max_pixels=1000, max_dimension_pixels=100, max_encoded_bytes=3000
        )
        is None
    )
    assert huge_page.requested_dpi is None

    encoded_page = _VisionPage(72, 72, encoded=b"x" * 101)
    fake_fitz(_document(encoded_page))
    assert (
        pdf_first_page_to_image_payload(
            tmp_path / "encoded.pdf", dpi=10, max_pixels=100, max_dimension_pixels=10, max_encoded_bytes=100
        )
        is None
    )
