"""Value objects and path validation used by the rename workflow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..infrastructure.files import is_path_within

MAX_RENAME_RETRIES = 20
type ExpectedSourceIdentity = tuple[int, int, int, int]


@dataclass(frozen=True)
class RenameApplyOptions:
    """Options controlling backup, plan, dry-run, naming limits, and post-rename work."""

    plan_file_path: Path | str | None = None
    plan_entries: list[dict[str, str]] | None = None
    dry_run: bool = False
    backup_dir: Path | str | None = None
    on_success: Callable[[Path, Path, str], None] | None = None
    max_filename_chars: int | None = None
    exact_target: bool = False
    expected_source_identity: ExpectedSourceIdentity | None = None


@dataclass(frozen=True)
class RenameAttemptState:
    """Current collision candidate and suffix counter for a rename attempt."""

    current_base: str
    target: Path
    counter: int


@dataclass(frozen=True)
class RenameRetryContext:
    """Source, base name, and suffix retained across collision retries."""

    file_path: Path
    base: str
    suffix: str


def validate_path_within_parent(path: Path, parent: Path) -> Path:
    """Ensure a resolved path stays under its expected parent."""
    resolved = path.resolve()
    parent_resolved = parent.resolve()
    if not is_path_within(path, parent):
        raise ValueError(f"Path traversal detected: {path} resolves to {resolved}, which is outside {parent_resolved}")
    return resolved
