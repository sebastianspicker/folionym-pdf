"""Browser thumbnail cache: pixel reuse, byte bounds, source rechecks, and HTTP error mapping."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import HTTPException

from folionym.application.models import FileFingerprint, PreviewItem, PreviewPlan, PreviewStatus
from folionym.interfaces.web import thumbnails
from folionym.settings import RenamerConfig


def _plan(tmp_path: Path) -> PreviewPlan:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"synthetic")
    item = PreviewItem(
        id="item",
        source=source,
        proposed_base="invoice",
        metadata={"summary": "x" * 10000},
        status=PreviewStatus.READY,
        included=True,
        fingerprint=FileFingerprint.capture(source),
    )
    return PreviewPlan("plan", tmp_path, "directory", RenamerConfig(), (item,), datetime.now(UTC))


def test_thumbnail_cache_reuses_pixels_bounds_bytes_and_rechecks_source(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    rendered: list[str] = []
    cache = thumbnails.ThumbnailCache(
        max_entries=2, max_bytes=5, renderer=lambda item: rendered.append(item.id) or b"image"
    )
    assert cache.get(plan, "item") == cache.get(plan, "item") == b"image"
    assert rendered == ["item"]
    # The five-byte budget holds one image, so caching another plan's image evicts the first.
    cache.get(replace(plan, id="another"), "item")
    assert rendered == ["item", "item"]
    assert cache.get(plan, "item") == b"image"
    assert rendered == ["item", "item", "item"]
    assert cache.get(plan, "item") == b"image"
    assert rendered == ["item", "item", "item"]
    plan.items[0].source.write_bytes(b"changed source")
    with pytest.raises(HTTPException) as error:
        cache.get(plan, "item")
    assert error.value.status_code == 409


def test_unrenderable_thumbnail_maps_to_http_not_found(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    with pytest.raises(HTTPException) as error:
        thumbnails.ThumbnailCache().get(plan, "item")
    assert error.value.status_code == 404
