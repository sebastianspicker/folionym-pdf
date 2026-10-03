"""Stable public facade for filename sanitization and atomic PDF renames."""

from ..infrastructure.filenames import (
    FILENAME_RESERVED_WIN,
    FILENAME_UNSAFE_RE,
    MAX_LLM_FILENAME_LEN,
    sanitize_filename_base,
    sanitize_filename_from_llm,
)
from ..infrastructure.files import is_path_within
from .execution import apply_single_rename
from .options import MAX_RENAME_RETRIES, RenameApplyOptions, RenameAttemptState, RenameRetryContext

__all__ = [
    "FILENAME_RESERVED_WIN",
    "FILENAME_UNSAFE_RE",
    "MAX_LLM_FILENAME_LEN",
    "MAX_RENAME_RETRIES",
    "RenameApplyOptions",
    "RenameAttemptState",
    "RenameRetryContext",
    "apply_single_rename",
    "is_path_within",
    "sanitize_filename_base",
    "sanitize_filename_from_llm",
]
