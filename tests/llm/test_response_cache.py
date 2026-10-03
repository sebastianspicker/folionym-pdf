"""Response-cache resource bounds, legacy-entry handling, expiry, and the shared-cache registry."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from folionym.llm import cache as cache_module
from folionym.llm.cache import ResponseCache, ResponseCacheLimits, get_shared_response_cache


def _entry_path(cache_dir: Path, key: str) -> Path:
    """Return the namespaced on-disk file for a non-hash key (the persisted cache layout)."""
    return cache_dir / f"folionym-{hashlib.sha256(key.encode('utf-8')).hexdigest()}.json"


def _legacy_entry_path(cache_dir: Path, key: str) -> Path:
    """Return the pre-namespace on-disk file that is only read for compatibility."""
    return cache_dir / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.json"


def test_response_cache_bounds_memory_by_entries_and_utf8_bytes() -> None:
    by_entries = ResponseCache(limits=ResponseCacheLimits(max_memory_entries=2, max_memory_bytes=1000))
    for key, value in (("a", "1111"), ("b", "2222"), ("c", "3333")):
        by_entries.set(key, value)
    assert by_entries.get("a") is None
    assert by_entries.get("b") == "2222"
    assert by_entries.get("c") == "3333"

    # Each entry costs its UTF-8 key plus value bytes (5), so 12 bytes hold two entries.
    by_bytes = ResponseCache(limits=ResponseCacheLimits(max_memory_entries=10, max_memory_bytes=12))
    for key, value in (("a", "1111"), ("b", "2222"), ("c", "3333")):
        by_bytes.set(key, value)
    assert by_bytes.get("a") is None
    assert by_bytes.get("b") == "2222"
    assert by_bytes.get("c") == "3333"

    # Multi-byte characters are measured in UTF-8 bytes, not characters.
    multibyte = ResponseCache(limits=ResponseCacheLimits(max_memory_entries=10, max_memory_bytes=12))
    multibyte.set("k", "ü" * 6)
    assert multibyte.get("k") is None


def test_oversized_update_invalidates_previous_memory_and_disk_value(tmp_path: Path) -> None:
    cache = ResponseCache(
        tmp_path,
        limits=ResponseCacheLimits(max_memory_entries=2, max_memory_bytes=20, max_disk_bytes=300),
    )
    cache.set("key", "old")
    disk_path = _entry_path(tmp_path, "key")
    assert disk_path.exists()

    cache.set("key", "x" * 1000)

    assert cache.get("key") is None
    assert not disk_path.exists()


def test_new_format_write_prevents_stale_legacy_value_resurrection(tmp_path: Path) -> None:
    limits = ResponseCacheLimits(max_memory_entries=2, max_memory_bytes=20, max_disk_bytes=400)
    cache = ResponseCache(tmp_path, limits=limits)
    legacy_path = _legacy_entry_path(tmp_path, "key")
    legacy_path.write_text('{"value":"old"}', encoding="utf-8")
    assert cache.get("key") == "old"

    cache.set("key", "x" * 1000)

    assert cache.get("key") is None
    assert legacy_path.read_text(encoding="utf-8") == '{"value":"old"}'
    restarted = ResponseCache(tmp_path, limits=limits)
    assert restarted.get("key") is None


def test_generation_marker_stops_legacy_reads_in_preexisting_cache_instances(tmp_path: Path) -> None:
    limits = ResponseCacheLimits(max_memory_bytes=20, max_disk_bytes=400)
    first = ResponseCache(tmp_path, limits=limits)
    second = ResponseCache(tmp_path, limits=limits)
    legacy_path = _legacy_entry_path(tmp_path, "key")
    legacy_path.write_text('{"value":"old"}', encoding="utf-8")
    assert second.get("key") == "old"

    first.set("key", "x" * 1000)

    assert first.get("key") is None
    assert second.get("key") is None


def test_response_cache_bounds_disk_without_touching_unrelated_files(tmp_path: Path) -> None:
    unrelated = tmp_path / "personal.json"
    unrelated.write_text("keep", encoding="utf-8")
    symlink = tmp_path / ("f" * 64 + ".json")
    symlink.symlink_to(unrelated)
    foreign_hash = tmp_path / ("e" * 64 + ".json")
    foreign_hash.write_text('{"value":"foreign"}', encoding="utf-8")
    foreign_namespaced = tmp_path / ("folionym-" + "d" * 64 + ".json")
    foreign_namespaced.write_text('{"value":"still foreign"}', encoding="utf-8")
    cache = ResponseCache(
        tmp_path,
        limits=ResponseCacheLimits(max_memory_entries=0, max_disk_entries=2, max_disk_bytes=10_000),
    )

    for key in ("one", "two", "three"):
        cache.set(key, key)

    hashed_entries = [
        entry
        for entry in tmp_path.iterdir()
        if entry.name.startswith("folionym-")
        and len(entry.name) == 78
        and entry != foreign_namespaced
        and not entry.is_symlink()
        and entry.suffix == ".json"
    ]
    assert len(hashed_entries) == 2
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert symlink.is_symlink()
    assert foreign_hash.read_text(encoding="utf-8") == '{"value":"foreign"}'
    assert foreign_namespaced.read_text(encoding="utf-8") == '{"value":"still foreign"}'


def test_disk_pruning_uses_bounded_prefix_and_rejects_special_files(tmp_path: Path) -> None:
    limits = ResponseCacheLimits(max_disk_bytes=300)
    path = _entry_path(tmp_path, "large")
    payload = (
        b'{"format": "folionym-response-cache-v1",'
        + b'"created_at":0,"value":"'
        + b"x" * 1000
        + b'","value_sha256":"unused"}'
    )
    path.write_bytes(payload)
    fifo: Path | None = tmp_path / ("folionym-" + "c" * 64 + ".json")
    try:
        os.mkfifo(fifo)
    except AttributeError, OSError:
        fifo = None

    # Opening a cache over an existing directory prunes it.
    ResponseCache(tmp_path, limits=limits)

    assert not path.exists()
    if fifo is not None:
        assert fifo.exists()


def test_response_cache_ttl_expires_memory_and_disk(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    now = 10_000.0
    monkeypatch.setattr(cache_module.time, "time", lambda: now)
    cache = ResponseCache(tmp_path, limits=ResponseCacheLimits(ttl_s=5))
    cache.set("key", "value")
    disk_path = _entry_path(tmp_path, "key")
    assert disk_path.exists()

    now += 6

    assert cache.get("key") is None
    assert not disk_path.exists()


def test_shared_response_cache_registry_is_bounded(tmp_path: Path) -> None:
    limits = ResponseCacheLimits(max_disk_entries=0, max_disk_bytes=0)
    caches = [get_shared_response_cache(tmp_path / str(number), limits=limits) for number in range(40)]

    # The sixteen most recently used caches are still shared; older ones were evicted.
    assert all(
        get_shared_response_cache(tmp_path / str(number), limits=limits) is caches[number] for number in range(24, 40)
    )
    assert get_shared_response_cache(tmp_path / "23", limits=limits) is not caches[23]
    assert get_shared_response_cache(tmp_path / "0", limits=limits) is not caches[0]
