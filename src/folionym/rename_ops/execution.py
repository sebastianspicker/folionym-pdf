"""Collision retries, preview planning, and callback handling for renames."""

from __future__ import annotations

import errno
import logging
import os
from collections.abc import Callable
from pathlib import Path

from ..infrastructure.files import open_regular_file_no_follow
from .backups import _write_backup
from .filesystem import (
    _copy_to_reserved_target_then_unlink,
    _rename_without_overwrite,
    _validate_expected_identity,
)
from .options import (
    MAX_RENAME_RETRIES,
    RenameApplyOptions,
    RenameAttemptState,
    RenameRetryContext,
    validate_path_within_parent,
)

logger = logging.getLogger("folionym.rename_ops")


def apply_single_rename(file_path: Path, base: str, options: RenameApplyOptions) -> tuple[bool, Path]:
    """Apply one rename with atomic collision retries, backup, plan, and dry-run support."""
    state, retry_context = _initialize_rename_attempt(file_path, base)
    source_fd: int | None = None
    try:
        if not options.dry_run and not options.plan_file_path:
            source_fd = open_regular_file_no_follow(file_path)
            _validate_expected_identity(os.fstat(source_fd), options.expected_source_identity, file_path)
            _write_backup(file_path, options.backup_dir, source_fd=source_fd)
            if os.name == "nt":
                os.close(source_fd)
                source_fd = None
        return _run_rename_attempts(retry_context, state, options, source_fd=source_fd)
    finally:
        if source_fd is not None:
            os.close(source_fd)


def apply_exact_rename(source: Path, target: Path) -> None:
    """Rename within one directory without overwriting or choosing another target."""
    validate_path_within_parent(target, source.parent)
    if source.parent.resolve() != target.parent.resolve():
        raise ValueError(f"Cross-directory rename denied: {source} -> {target}")
    _rename_without_overwrite(source, target)


def _initialize_rename_attempt(file_path: Path, base: str) -> tuple[RenameAttemptState, RenameRetryContext]:
    """Build and validate the first collision candidate for a source file."""
    suffix = file_path.suffix
    state = RenameAttemptState(base, file_path.with_name(base + suffix), 0)
    validate_path_within_parent(state.target, file_path.parent)
    return state, RenameRetryContext(file_path, base, suffix)


def _run_rename_attempts(
    retry_context: RenameRetryContext,
    state: RenameAttemptState,
    options: RenameApplyOptions,
    *,
    source_fd: int | None,
) -> tuple[bool, Path]:
    """Retry atomic rename candidates until one succeeds or the limit is reached."""
    for _attempt in range(MAX_RENAME_RETRIES):
        try:
            return _apply_rename_attempt(retry_context.file_path, state, options, source_fd=source_fd)
        except (FileExistsError, OSError) as error:
            outcome = _handle_rename_attempt_error(retry_context, state, options, error, source_fd=source_fd)
            if not isinstance(outcome, RenameAttemptState):
                return outcome
            state = outcome
    logger.error(
        "Rename failed after %d attempts (target already exists): %s -> %s",
        MAX_RENAME_RETRIES,
        retry_context.file_path,
        state.target,
    )
    return False, state.target


def _apply_rename_attempt(
    file_path: Path,
    state: RenameAttemptState,
    options: RenameApplyOptions,
    *,
    source_fd: int | None,
) -> tuple[bool, Path]:
    """Record, simulate, or perform one no-overwrite rename candidate."""
    if (options.dry_run or options.plan_file_path) and os.path.lexists(state.target):
        raise FileExistsError(f"Target already exists: {state.target}")
    if _record_rename_plan(file_path, state.target, options):
        return True, state.target
    if not options.dry_run:
        _rename_without_overwrite(
            file_path,
            state.target,
            source_fd,
            expected_identity=options.expected_source_identity,
        )
        _notify_rename_success(options.on_success, file_path, state.target, state.current_base)
    return True, state.target


def _record_rename_plan(file_path: Path, target: Path, options: RenameApplyOptions) -> bool:
    """Record a planned rename and report whether filesystem work should stop."""
    if not options.plan_file_path:
        return False
    if options.plan_entries is not None:
        options.plan_entries.append({"old": str(file_path), "new": str(target)})
    logger.info("Plan: %s -> %s", file_path.name, target.name)
    return True


def _handle_rename_attempt_error(
    retry_context: RenameRetryContext,
    state: RenameAttemptState,
    options: RenameApplyOptions,
    error: FileExistsError | OSError,
    *,
    source_fd: int | None,
) -> RenameAttemptState | tuple[bool, Path]:
    """Translate an attempt error into a retry candidate, result, or raised failure."""
    if _is_target_exists_error(error):
        return _collision_outcome(retry_context, state, options)
    if _is_filename_too_long_error(error):
        message = f"Filename too long: {state.target}. Shorten the summary or keywords."
        raise OSError(errno.ENAMETOOLONG, message) from error
    if error.errno == errno.EXDEV:
        return _handle_cross_filesystem_rename(retry_context.file_path, state, options, source_fd=source_fd)
    raise error


def _collision_outcome(
    retry_context: RenameRetryContext, state: RenameAttemptState, options: RenameApplyOptions
) -> RenameAttemptState | tuple[bool, Path]:
    """Return an exact-target collision or the next suffixed candidate."""
    if options.exact_target:
        return False, state.target
    current_base, target = _collision_target(
        retry_context.file_path,
        retry_context.base,
        retry_context.suffix,
        state.counter + 1,
        options.max_filename_chars,
    )
    return RenameAttemptState(current_base, target, state.counter + 1)


def _collision_target(
    file_path: Path, base: str, suffix: str, counter: int, max_filename_chars: int | None
) -> tuple[str, Path]:
    """Construct a collision suffix while respecting character and byte limits."""
    suffix_str = f"_{counter}"
    effective_base = _truncate_base_for_limit(base, suffix, suffix_str, max_filename_chars)
    current_base = _truncate_base_for_bytes(effective_base, suffix, suffix_str)
    return current_base, file_path.with_name(current_base + suffix)


def _truncate_base_for_limit(base: str, suffix: str, suffix_str: str, limit: int | None) -> str:
    """Trim a base so its configured character limit includes suffixes."""
    if limit and limit > len(suffix_str + suffix):
        return base[: limit - len(suffix_str + suffix)]
    return base


def _truncate_base_for_bytes(base: str, suffix: str, suffix_str: str) -> str:
    """Trim a base to the portable 255-byte filename ceiling."""
    current_base = f"{base}{suffix_str}"
    if len((current_base + suffix).encode("utf-8")) <= 255:
        return current_base
    max_base_bytes = 255 - len((suffix_str + suffix).encode("utf-8"))
    return f"{base.encode('utf-8')[:max_base_bytes].decode('utf-8', errors='ignore')}{suffix_str}"


def _is_target_exists_error(exc: BaseException) -> bool:
    """Recognize platform-specific errors that mean the target is occupied."""
    return isinstance(exc, FileExistsError) or (
        isinstance(exc, OSError)
        and (exc.errno == errno.EEXIST or (os.name == "nt" and exc.errno == getattr(errno, "EACCES", None)))
    )


def _is_filename_too_long_error(error: OSError) -> bool:
    """Return whether an OS error reports an overlong filename."""
    return error.errno == errno.ENAMETOOLONG


def _handle_cross_filesystem_rename(
    file_path: Path,
    state: RenameAttemptState,
    options: RenameApplyOptions,
    *,
    source_fd: int | None,
) -> tuple[bool, Path]:
    """Complete a cross-filesystem rename through the guarded copy fallback."""
    if options.dry_run:
        return True, state.target
    _copy_to_reserved_target_then_unlink(
        file_path,
        state.target,
        source_fd,
        expected_identity=options.expected_source_identity,
    )
    _notify_rename_success(options.on_success, file_path, state.target, state.current_base)
    return True, state.target


def _notify_rename_success(
    on_success: Callable[[Path, Path, str], None] | None, file_path: Path, target: Path, current_base: str
) -> None:
    """Invoke post-rename work without turning its failure into rename failure."""
    if on_success is None:
        return
    try:
        on_success(file_path, target, current_base)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Rename completed but its post-rename callback failed: %s -> %s", file_path, target)
