"""Response caching for repeated LLM work.

Cache entries always live in memory for the current process. When ``cache_dir``
is set, entries are also persisted on disk as individual JSON files.
"""

from __future__ import annotations

import errno
import hashlib
import json
import logging
import os
import stat
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from ..infrastructure.private_io import atomic_write_private_text
from ..settings.models import (
    DEFAULT_CACHE_MAX_DISK_BYTES,
    DEFAULT_CACHE_MAX_DISK_ENTRIES,
    DEFAULT_CACHE_MAX_MEMORY_BYTES,
    DEFAULT_CACHE_MAX_MEMORY_ENTRIES,
    DEFAULT_CACHE_TTL_S,
)

_HASH_CHUNK_BYTES = 1024 * 1024
_OWNER_ONLY_DIR_MODE = 0o700
_OWNER_ONLY_FILE_MODE = 0o600
_CACHE_FORMAT = "folionym-response-cache-v1"
_CACHE_FILE_PREFIX = "folionym-"
_CACHE_GENERATION_MARKER = ".folionym-response-cache-v1"
_MANAGED_PAYLOAD_PREFIX = f'{{"format": "{_CACHE_FORMAT}",'.encode()
_MAX_SHARED_CACHES = 16
logger = logging.getLogger(__name__)
_shared_caches: OrderedDict[tuple[str, int, int, int, int, float], ResponseCache] = OrderedDict()
_shared_caches_lock = threading.Lock()


@dataclass(frozen=True)
class ResponseCacheLimits:
    """Bound in-process and persistent response-cache resources."""

    max_memory_entries: int = DEFAULT_CACHE_MAX_MEMORY_ENTRIES
    max_memory_bytes: int = DEFAULT_CACHE_MAX_MEMORY_BYTES
    max_disk_entries: int = DEFAULT_CACHE_MAX_DISK_ENTRIES
    max_disk_bytes: int = DEFAULT_CACHE_MAX_DISK_BYTES
    ttl_s: float = DEFAULT_CACHE_TTL_S


class CachePermissionError(RuntimeError):
    """Raised when a persistent cache path cannot be restricted to the owner."""

    def __init__(self, path: Path, mode: int, original: BaseException) -> None:
        """Record the path and requested mode for a cache permission failure."""
        self.path = path
        self.mode = mode
        super().__init__(f"Could not set owner-only permissions {mode:o} on {path}: {original}")


def _set_owner_only_permissions(path: Path, mode: int) -> None:
    """Restrict local document-derived cache data to the current owner."""
    try:
        path.chmod(mode)
    except (OSError, NotImplementedError) as exc:
        raise CachePermissionError(path, mode, exc) from exc


def _write_private_text(path: Path, text: str) -> None:
    """Write a cache entry atomically with owner-only permissions."""
    # fmt: off
    try:
        atomic_write_private_text(
            path,
            text,
            before_write=lambda temp_path: _set_owner_only_permissions(temp_path, _OWNER_ONLY_FILE_MODE),
        )
    except (OSError, CachePermissionError):
        raise
    # fmt: on


def _file_identity(status: os.stat_result) -> tuple[int, int, int, int]:
    """Return fields used to detect path or file changes during hashing."""
    return (status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns)


class ResponseCache:
    """Cache string responses in memory and optionally on disk."""

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        *,
        limits: ResponseCacheLimits | None = None,
    ) -> None:
        """Initialize an in-memory cache and enable private disk persistence when possible."""
        effective_limits = limits or ResponseCacheLimits()
        self.max_memory_entries = max(0, int(effective_limits.max_memory_entries))
        self.max_memory_bytes = max(0, int(effective_limits.max_memory_bytes))
        self.max_disk_entries = max(0, int(effective_limits.max_disk_entries))
        self.max_disk_bytes = max(0, int(effective_limits.max_disk_bytes))
        self.ttl_s = max(0.0, float(effective_limits.ttl_s))
        requested_cache_dir = (
            Path(cache_dir).expanduser()
            if cache_dir and self.max_disk_entries > 0 and self.max_disk_bytes > 0
            else None
        )
        self.cache_dir = None
        if requested_cache_dir is not None:
            try:
                requested_cache_dir.mkdir(parents=True, mode=_OWNER_ONLY_DIR_MODE, exist_ok=True)
                _set_owner_only_permissions(requested_cache_dir, _OWNER_ONLY_DIR_MODE)
            except (OSError, CachePermissionError) as exc:
                logger.warning("Persistent LLM cache disabled: %s", exc)
            else:
                self.cache_dir = requested_cache_dir
        self._memory: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._memory_bytes = 0
        self._lock = threading.Lock()
        self._legacy_reads_enabled = bool(
            self.cache_dir is not None and not (self.cache_dir / _CACHE_GENERATION_MARKER).exists()
        )
        self._prune_disk()

    @staticmethod
    def build_file_key(path: str | Path) -> str:
        """Hash the complete file, failing if its path or opened file changes during the read."""
        file_path = Path(path)
        before = file_path.stat()
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            if _file_identity(opened) != _file_identity(before):
                raise OSError(errno.EAGAIN, f"File changed before cache hashing began: {file_path}")
            while chunk := handle.read(_HASH_CHUNK_BYTES):
                digest.update(chunk)
            after_read = os.fstat(handle.fileno())
        after_path = file_path.stat()
        expected_identity = _file_identity(before)
        if _file_identity(after_read) != expected_identity or _file_identity(after_path) != expected_identity:
            raise OSError(errno.EAGAIN, f"File changed while building cache key: {file_path}")
        return digest.hexdigest()

    @staticmethod
    def derive_response_key(
        file_key: str,
        *,
        operation: str,
        model: str = "",
        language: str = "",
        extra: str = "",
    ) -> str:
        """Derive a response key from the base file fingerprint plus request metadata."""
        payload = "\0".join([file_key, operation, model, language, extra])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _disk_path(self, key: str) -> Path | None:
        """Return the sanitized cache-entry path, or None when disk caching is disabled."""
        with self._lock:
            cache_dir = self.cache_dir
        if cache_dir is None:
            return None
        if len(key) == 64 and all(character in "0123456789abcdef" for character in key):
            disk_key = key
        else:
            disk_key = hashlib.sha256(key.encode("utf-8", errors="surrogatepass")).hexdigest()
        return cache_dir / f"{_CACHE_FILE_PREFIX}{disk_key}.json"

    def _legacy_disk_path(self, key: str) -> Path | None:
        """Return the pre-namespace cache path for read-only compatibility."""
        disk_path = self._disk_path(key)
        if disk_path is None:
            return None
        return disk_path.with_name(disk_path.name.removeprefix(_CACHE_FILE_PREFIX))

    def get(self, key: str) -> str | None:
        """Return a memory or valid on-disk cached string; treat unreadable entries as misses."""
        now = time.time()
        self._legacy_fallback_allowed()
        with self._lock:
            cached = self._memory.get(key)
            if cached is not None:
                value, created_at = cached
                if self._expired(created_at, now=now):
                    del self._memory[key]
                    self._memory_bytes -= self._entry_memory_bytes(key, value)
                else:
                    self._memory.move_to_end(key)
                    return value
        disk_path = self._disk_path(key)
        if disk_path is not None and disk_path.exists():
            return self._remember_disk_value(key, disk_path, now=now, managed=True)
        legacy_path = self._legacy_disk_path(key) if self._legacy_fallback_allowed() else None
        if legacy_path is None or not legacy_path.exists():
            return None
        return self._remember_disk_value(key, legacy_path, now=now, managed=False)

    def _legacy_fallback_allowed(self) -> bool:
        """Observe generation changes made by another process before reading a legacy entry."""
        with self._lock:
            cache_dir = self.cache_dir
            if not self._legacy_reads_enabled or cache_dir is None:
                return False
        if (cache_dir / _CACHE_GENERATION_MARKER).exists():
            with self._lock:
                self._legacy_reads_enabled = False
                self._memory.clear()
                self._memory_bytes = 0
            return False
        return True

    def _remember_disk_value(self, key: str, disk_path: Path, *, now: float, managed: bool) -> str | None:
        """Validate one disk entry and promote it to the bounded memory cache."""
        disk_value = self._read_disk_value(disk_path, now=now, managed=managed)
        if disk_value is None:
            return None
        if not managed and not self._legacy_fallback_allowed():
            return None
        value, created_at = disk_value
        with self._lock:
            self._remember(key, value, created_at)
        return value

    def _read_disk_value(self, disk_path: Path, *, now: float, managed: bool) -> tuple[str, float] | None:
        """Read and validate one persistent cache entry."""
        payload = self._read_disk_payload(disk_path)
        if payload is None:
            return None
        value = self._validated_payload_value(payload, managed=managed)
        if value is None:
            return None
        created_at = self._disk_created_at(disk_path, payload)
        if created_at is None:
            return None
        if self._expired(created_at, now=now):
            if managed:
                self._unlink_cache_entry(disk_path)
            return None
        return value, created_at

    @classmethod
    def _validated_payload_value(cls, payload: dict[str, object], *, managed: bool) -> str | None:
        """Return a valid managed or legacy response value."""
        if managed and not cls._is_managed_payload(payload):
            return None
        value = payload.get("value")
        if not isinstance(value, str):
            return None
        expected_hash = payload.get("value_sha256")
        if isinstance(expected_hash, str) and hashlib.sha256(value.encode("utf-8")).hexdigest() != expected_hash:
            return None
        return value

    @staticmethod
    def _is_managed_payload(payload: dict[str, object]) -> bool:
        """Return whether a JSON object has the complete Folionym cache format marker and integrity fields."""
        value = payload.get("value")
        created_at = payload.get("created_at")
        value_hash = payload.get("value_sha256")
        return bool(
            payload.get("format") == _CACHE_FORMAT
            and isinstance(value, str)
            and isinstance(created_at, int | float)
            and isinstance(value_hash, str)
            and hashlib.sha256(value.encode("utf-8")).hexdigest() == value_hash
        )

    def _read_disk_payload(self, disk_path: Path) -> dict[str, object] | None:
        """Read bounded JSON from one regular, non-symlink cache file."""
        opened = self._open_verified_regular(disk_path)
        if opened is None:
            return None
        descriptor, status = opened
        if status.st_size > self.max_disk_bytes:
            os.close(descriptor)
            return None
        try:
            with os.fdopen(descriptor, encoding="utf-8") as handle:
                payload = json.load(handle)
        except OSError, UnicodeDecodeError, json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    @staticmethod
    def _open_verified_regular(path: Path) -> tuple[int, os.stat_result] | None:
        """Open one unchanged regular file without following symlinks or blocking on special files."""
        try:
            before = path.lstat()
        except OSError:
            return None
        if not stat.S_ISREG(before.st_mode):
            return None
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError:
            return None
        try:
            opened = os.fstat(descriptor)
        except OSError:
            os.close(descriptor)
            return None
        if not stat.S_ISREG(opened.st_mode) or _file_identity(opened) != _file_identity(before):
            os.close(descriptor)
            return None
        return descriptor, opened

    @classmethod
    def _managed_entry_status(cls, path: Path) -> os.stat_result | None:
        """Validate ownership from a fixed bounded prefix and return entry metadata."""
        opened = cls._open_verified_regular(path)
        if opened is None:
            return None
        descriptor, status = opened
        try:
            prefix = os.read(descriptor, len(_MANAGED_PAYLOAD_PREFIX))
        except OSError:
            return None
        finally:
            os.close(descriptor)
        return status if prefix == _MANAGED_PAYLOAD_PREFIX else None

    @staticmethod
    def _disk_created_at(disk_path: Path, payload: dict[str, object]) -> float | None:
        """Read a stored creation timestamp, falling back to the file timestamp for legacy entries."""
        created_at_value = payload.get("created_at")
        try:
            return float(created_at_value) if isinstance(created_at_value, int | float) else disk_path.stat().st_mtime
        except OSError:
            return None

    def set(self, key: str, value: str) -> None:
        """Cache a response in memory and persist it privately when disk caching is enabled."""
        created_at = time.time()
        with self._lock:
            self._remember(key, value, created_at)
        disk_path = self._disk_path(key)
        if disk_path is None or self.max_disk_entries == 0 or self.max_disk_bytes == 0:
            return
        if not self._disable_legacy_reads():
            return
        payload = json.dumps(
            {
                "format": _CACHE_FORMAT,
                "created_at": created_at,
                "value": value,
                "value_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
            },
            ensure_ascii=False,
        )
        if len(payload.encode("utf-8")) > self.max_disk_bytes:
            self._unlink_managed_cache_entry(disk_path)
            return
        try:
            _write_private_text(disk_path, payload)
        except (OSError, CachePermissionError) as exc:
            logger.warning("Persistent LLM cache disabled: %s", exc)
            with self._lock:
                self.cache_dir = None
        else:
            self._prune_disk()

    def _disable_legacy_reads(self) -> bool:
        """Persist the transition to namespaced entries before any new-format write."""
        with self._lock:
            if not self._legacy_reads_enabled:
                return self.cache_dir is not None
            self._legacy_reads_enabled = False
            cache_dir = self.cache_dir
        if cache_dir is None:
            return False
        try:
            _write_private_text(cache_dir / _CACHE_GENERATION_MARKER, _CACHE_FORMAT)
        except (OSError, CachePermissionError) as exc:
            logger.warning("Persistent LLM cache disabled: %s", exc)
            with self._lock:
                self.cache_dir = None
            return False
        return True

    def _expired(self, created_at: float, *, now: float) -> bool:
        """Return whether an entry is older than the configured TTL."""
        return self.ttl_s > 0 and now - created_at > self.ttl_s

    def _remember(self, key: str, value: str, created_at: float) -> None:
        """Store one memory entry and enforce the LRU entry bound under the caller's lock."""
        entry_bytes = self._entry_memory_bytes(key, value)
        previous = self._memory.pop(key, None)
        if previous is not None:
            self._memory_bytes -= self._entry_memory_bytes(key, previous[0])
        if self.max_memory_entries == 0 or self.max_memory_bytes == 0 or entry_bytes > self.max_memory_bytes:
            return
        self._memory[key] = (value, created_at)
        self._memory_bytes += entry_bytes
        self._memory.move_to_end(key)
        while len(self._memory) > self.max_memory_entries or self._memory_bytes > self.max_memory_bytes:
            old_key, (old_value, _created_at) = self._memory.popitem(last=False)
            self._memory_bytes -= self._entry_memory_bytes(old_key, old_value)

    @staticmethod
    def _entry_memory_bytes(key: str, value: str) -> int:
        """Measure the UTF-8 response payload and its lookup key for deterministic bounding."""
        return len(key.encode("utf-8", errors="surrogatepass")) + len(value.encode("utf-8"))

    @staticmethod
    def _unlink_cache_entry(path: Path) -> None:
        """Best-effort remove one regular cache entry."""
        try:
            if path.is_symlink():
                return
            path.unlink(missing_ok=True)
        except OSError:
            return

    def _unlink_managed_cache_entry(self, path: Path) -> None:
        """Remove an entry only after validating Folionym's format marker and integrity fields."""
        if self._managed_entry_status(path) is not None:
            self._unlink_cache_entry(path)

    def _prune_disk(self) -> None:
        """Bound persistent JSON entries by TTL, count, and aggregate bytes."""
        cache_dir = self.cache_dir
        if cache_dir is None:
            return
        try:
            candidates = list(cache_dir.iterdir())
        except OSError:
            return
        now = time.time()
        retained: list[tuple[int, int, Path]] = []
        for entry in candidates:
            disk_key = entry.name.removeprefix(_CACHE_FILE_PREFIX).removesuffix(".json")
            if (
                not entry.name.startswith(_CACHE_FILE_PREFIX)
                or not entry.name.endswith(".json")
                or len(disk_key) != 64
                or any(character not in "0123456789abcdef" for character in disk_key)
            ):
                continue
            status = self._managed_entry_status(entry)
            if status is None:
                continue
            if self._expired(status.st_mtime, now=now):
                self._unlink_cache_entry(entry)
                continue
            retained.append((status.st_mtime_ns, status.st_size, entry))
        retained.sort(reverse=True)
        total_bytes = 0
        kept_entries = 0
        for _mtime, size, entry in retained:
            if kept_entries >= self.max_disk_entries or total_bytes + size > self.max_disk_bytes:
                self._unlink_cache_entry(entry)
                continue
            kept_entries += 1
            total_bytes += size


def get_shared_response_cache(
    cache_dir: str | Path | None = None,
    *,
    limits: ResponseCacheLimits | None = None,
) -> ResponseCache:
    """Return a shared cache instance for the current process."""
    effective_limits = limits or ResponseCacheLimits()
    path_key = "<memory>" if cache_dir is None else str(Path(cache_dir).expanduser())
    key = (
        path_key,
        effective_limits.max_memory_entries,
        effective_limits.max_memory_bytes,
        effective_limits.max_disk_entries,
        effective_limits.max_disk_bytes,
        effective_limits.ttl_s,
    )
    with _shared_caches_lock:
        cache = _shared_caches.get(key)
        if cache is None:
            cache = ResponseCache(
                cache_dir=cache_dir,
                limits=effective_limits,
            )
            _shared_caches[key] = cache
            while len(_shared_caches) > _MAX_SHARED_CACHES:
                _shared_caches.popitem(last=False)
        else:
            _shared_caches.move_to_end(key)
        return cache
