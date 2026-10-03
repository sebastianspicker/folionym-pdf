"""Immediate single-file rename use case: suggest, then rename to a unique available name."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..infrastructure.filenames import sanitize_filename_base
from ..rename_ops import RenameApplyOptions, apply_single_rename
from ..settings import RenamerConfig
from .hooks import make_post_rename_success_callback
from .proposals import suggest_rename_for_file


@dataclass(frozen=True)
class SingleFileResult:
    """Outcome of one immediate rename.

    ``error`` is set when no proposal could be produced. ``base`` is None when the file
    had no extractable content (skipped). Otherwise ``success`` reports whether the
    rename happened and ``target`` is the path it landed on.
    """

    base: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    error: BaseException | None = None
    success: bool = False
    target: Path | None = None


def rename_single_file(path: Path, config: RenamerConfig) -> SingleFileResult:
    """Suggest a name for one file and rename it now, running configured post-rename actions."""
    new_base, meta, err = suggest_rename_for_file(path, config)
    if err is not None:
        return SingleFileResult(error=err)
    if new_base is None:
        return SingleFileResult()
    metadata = meta or {}
    success, target = apply_single_rename(
        path,
        sanitize_filename_base(new_base),
        RenameApplyOptions(
            plan_file_path=None,
            plan_entries=[],
            dry_run=False,
            backup_dir=config.output.paths.backup_dir,
            on_success=make_post_rename_success_callback(config, metadata, []),
            max_filename_chars=config.output.naming.max_filename_chars,
        ),
    )
    return SingleFileResult(base=new_base, metadata=metadata, success=success, target=target)
