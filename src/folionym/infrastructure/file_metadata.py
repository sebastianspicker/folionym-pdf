"""Best-effort preservation of extended attributes and creation date, plus no-replace rename."""

from __future__ import annotations

import ctypes
import ctypes.util
import errno
import functools
import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)

_RENAME_EXCL_DARWIN = 0x4
_RENAME_NOREPLACE_LINUX = 1
_COPYFILE_XATTR = 1 << 2
_UNSUPPORTED_ERRNOS = frozenset({errno.ENOTSUP, errno.EOPNOTSUPP, errno.EINVAL, errno.ENOSYS})


@functools.cache
def _libc() -> ctypes.CDLL | None:
    name = ctypes.util.find_library("c")
    if name is None:
        return None
    try:
        return ctypes.CDLL(name, use_errno=True)
    except OSError:
        return None


@functools.cache
def _libc_function(name: str, argtypes: tuple[Any, ...]) -> Any | None:
    """Return a libc function with its signature set once, or None when it does not exist."""
    libc = _libc()
    function = getattr(libc, name, None) if libc is not None else None
    if function is not None:
        function.argtypes = list(argtypes)
        function.restype = ctypes.c_int
    return function


_RENAME_ARGTYPES = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
_FCOPYFILE_ARGTYPES = (ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)


def rename_no_replace(directory_fd: int, source_name: str, target_name: str) -> bool:
    """Atomically rename within one directory, refusing an existing target.

    Returns False when the platform or filesystem cannot do it, so callers can fall back.
    """
    if sys.platform == "darwin":
        function = _libc_function("renameatx_np", _RENAME_ARGTYPES)
        flag = _RENAME_EXCL_DARWIN
    elif sys.platform.startswith("linux"):
        function = _libc_function("renameat2", _RENAME_ARGTYPES)
        flag = _RENAME_NOREPLACE_LINUX
    else:
        return False
    if function is None:
        return False
    if function(directory_fd, os.fsencode(source_name), directory_fd, os.fsencode(target_name), flag) == 0:
        return True
    err = ctypes.get_errno()
    if err == errno.EEXIST:
        raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), target_name)
    if err in _UNSUPPORTED_ERRNOS:
        return False
    raise OSError(err, os.strerror(err), source_name)


def copy_file_metadata(source_fd: int, target_fd: int) -> None:
    """Copy extended attributes (and the creation date on macOS) without ever raising OSError."""
    try:
        if sys.platform == "darwin":
            _copy_darwin(source_fd, target_fd)
        elif sys.platform.startswith("linux"):
            _copy_linux_xattrs(source_fd, target_fd)
    except OSError as exc:
        logger.debug("Could not copy file metadata: %s", exc)


def _copy_darwin(source_fd: int, target_fd: int) -> None:
    fcopyfile = _libc_function("fcopyfile", _FCOPYFILE_ARGTYPES)
    if fcopyfile is not None and fcopyfile(source_fd, target_fd, None, _COPYFILE_XATTR) != 0:
        logger.debug("fcopyfile failed: errno %d", ctypes.get_errno())
    source = os.fstat(source_fd)
    target = os.fstat(target_fd)
    if source.st_birthtime < target.st_birthtime:
        # APFS moves the birth time back when mtime is set earlier.
        os.utime(target_fd, ns=(target.st_atime_ns, int(source.st_birthtime * 1e9)))
        os.utime(target_fd, ns=(target.st_atime_ns, target.st_mtime_ns))


def _copy_linux_xattrs(source_fd: int, target_fd: int) -> None:
    if sys.platform == "linux":
        for name in os.listxattr(source_fd):
            if name.startswith("user."):
                os.setxattr(target_fd, name, os.getxattr(source_fd, name))
