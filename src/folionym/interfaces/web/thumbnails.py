"""Bounded process-local thumbnails; PDF-derived pixels never persist to disk."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from threading import Lock
from time import monotonic

from fastapi import HTTPException

from ...application.models import FileFingerprint, PreviewItem, PreviewPlan
from ...extraction import (
    PageRenderError,
    PageRenderTooLargeError,
    PageRenderUnavailableError,
    render_first_page_thumbnail,
)


def render_thumbnail(item: PreviewItem) -> bytes:
    """Render one plan-owned PDF's first page, mapping render failures to HTTP errors."""
    try:
        return render_first_page_thumbnail(item.source)
    except PageRenderUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc
    except PageRenderTooLargeError as exc:
        raise HTTPException(413, str(exc)) from exc
    except PageRenderError as exc:
        raise HTTPException(404, str(exc)) from exc


class ThumbnailCache:
    """Reuse reviewed thumbnails within a byte, entry, and age budget."""

    def __init__(
        self,
        *,
        max_bytes: int = 16 * 1024 * 1024,
        max_entries: int = 128,
        ttl: float = 300,
        renderer: Callable[[PreviewItem], bytes] = render_thumbnail,
    ) -> None:
        if max_bytes < 1 or max_entries < 1 or ttl <= 0:
            raise ValueError("Thumbnail cache limits must be positive")
        self._max_bytes = max_bytes
        self._max_entries = max_entries
        self._ttl = ttl
        self._renderer = renderer
        self._bytes = 0
        self._entries: OrderedDict[tuple[str, int, str], tuple[float, bytes]] = OrderedDict()
        self._lock = Lock()

    def _prune(self, now: float) -> None:
        for key, (created, data) in list(self._entries.items()):
            if now - created >= self._ttl:
                self._entries.pop(key)
                self._bytes -= len(data)
        while self._bytes > self._max_bytes or len(self._entries) > self._max_entries:
            _key, (_created, data) = self._entries.popitem(last=False)
            self._bytes -= len(data)

    @staticmethod
    def _validate(item: PreviewItem) -> FileFingerprint:
        if item.fingerprint is None or not item.fingerprint.matches(item.source):
            raise HTTPException(409, "The source changed after Preview. Preview again.")
        return item.fingerprint

    def get(self, plan: PreviewPlan, item_id: str) -> bytes:
        item = next((candidate for candidate in plan.items if candidate.id == item_id), None)
        if item is None:
            raise HTTPException(404, "Preview item not found.")
        key = (plan.id, plan.revision, item.id)
        # Serializing rendering also bounds concurrent native pixmap allocations.
        with self._lock:
            self._validate(item)
            now = monotonic()
            self._prune(now)
            cached = self._entries.get(key)
            if cached is not None:
                self._entries.move_to_end(key)
                return cached[1]
            data = self._renderer(item)
            self._validate(item)
            if len(data) <= self._max_bytes:
                self._entries[key] = (now, data)
                self._bytes += len(data)
                self._prune(now)
            return data
