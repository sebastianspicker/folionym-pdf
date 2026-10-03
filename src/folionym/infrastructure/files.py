"""Filesystem safety checks shared across application boundaries."""

from __future__ import annotations

import errno
import os
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path


def reject_source_symlink(path: Path) -> None:
    """Reject a visible source symlink before extraction or mutation."""
    if path.is_symlink():
        raise OSError(errno.ELOOP, "Source PDF symbolic links are not supported", path)


def _open_path_without_symlinks(path: Path, *, directory: bool) -> int:
    """Open an absolute path one component at a time without following links."""
    absolute = Path(os.path.abspath(path))
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)

    if os.name == "nt" or not nofollow:
        return os.open(absolute, flags | nofollow)

    parts = absolute.parts
    if len(parts) < 2:
        if directory:
            return os.open(absolute, flags | nofollow)
        raise OSError(errno.EISDIR, "Expected a regular file", absolute)
    directory_fd = os.open(parts[0], os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow)
    try:
        for component in parts[1:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow,
                dir_fd=directory_fd,
            )
            os.close(directory_fd)
            directory_fd = next_fd
        return os.open(parts[-1], flags | nofollow, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)


def open_directory_no_follow(path: Path) -> int:
    """Open a directory while rejecting symbolic links in every path component."""
    fd = _open_path_without_symlinks(path, directory=True)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise NotADirectoryError(path)
    except BaseException:
        os.close(fd)
        raise
    return fd


def open_regular_file_no_follow(path: Path) -> int:
    """Open a regular file while rejecting symbolic links in every path component."""
    try:
        fd = _open_path_without_symlinks(path, directory=False)
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise OSError(errno.ELOOP, f"Source path changed or contains symbolic links: {path}") from exc
        raise
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(errno.EINVAL, "Source is not a regular file", path)
    except BaseException:
        os.close(fd)
        raise
    return fd


def read_regular_file_no_follow(path: Path) -> bytes:
    """Read one stable regular-file identity without reopening its pathname."""
    fd = open_regular_file_no_follow(path)
    try:
        before = os.fstat(fd)
        chunks: list[bytes] = []
        while chunk := os.read(fd, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(fd)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise OSError(errno.EBUSY, "Source changed while it was being read", path)
        return b"".join(chunks)
    finally:
        os.close(fd)


@contextmanager
def private_regular_file_snapshot(path: Path, *, suffix: str = "") -> Iterator[Path]:
    """Yield a private snapshot copied from a verified regular-file descriptor."""
    source_fd = open_regular_file_no_follow(path)
    snapshot_fd = -1
    snapshot: Path | None = None
    try:
        snapshot_fd, raw_snapshot = tempfile.mkstemp(prefix="folionym_source_", suffix=suffix)
        snapshot = Path(raw_snapshot).resolve(strict=True)
        before = os.fstat(source_fd)
        while chunk := os.read(source_fd, 1024 * 1024):
            view = memoryview(chunk)
            while view:
                written = os.write(snapshot_fd, view)
                view = view[written:]
        after = os.fstat(source_fd)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise OSError(errno.EBUSY, "Source changed while it was being copied", path)
        if os.name != "nt":
            os.fchmod(snapshot_fd, stat.S_IRUSR | stat.S_IWUSR)
        yield snapshot
    finally:
        os.close(source_fd)
        if snapshot_fd >= 0:
            os.close(snapshot_fd)
        if snapshot is not None:
            with suppress(OSError):
                snapshot.unlink()


def is_path_within(path: Path, root: Path) -> bool:
    """Return whether a resolved path is equal to or below a resolved root."""
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
        return resolved == root_resolved or resolved.is_relative_to(root_resolved)
    except OSError, ValueError:
        return False
