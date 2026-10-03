"""Batch rename orchestration and side-effect boundary.

This module coordinates discovery, extraction, filename generation, output
artifacts, and optional hooks for a batch run. Watch mode lives in
application/watch.py; pure naming decisions live in the naming package;
renames are delegated to the rename_ops package.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from ..extraction.pdf import NoTextExtractedError
from ..infrastructure.errors import COMMON_RECOVERABLE_EXCEPTIONS, DataFileError
from ..naming.rules import ProcessingRules
from ..rename_ops import (
    MAX_RENAME_RETRIES,
    RenameApplyOptions,
    apply_single_rename,
)
from ..settings import RenamerConfig
from .artifacts import (
    RenameOutputData,
    RenameSummaryData,
    append_export_row,
    write_rename_outputs,
    write_summary_json,
)
from .discovery import collect_sorted_pdf_files, load_effective_rules, resolve_rename_directory
from .hooks import make_post_rename_success_callback
from .models import Proposal
from .proposals import ProgressCallback, produce_proposals
from .scheduling import stop_requested

logger = logging.getLogger(__name__)
_RECOVERABLE_RENAME_EXCEPTIONS = (
    AttributeError,
    *COMMON_RECOVERABLE_EXCEPTIONS,
)


ConfirmCallback = Callable[[Path, str, dict[str, object]], str | None]
"""Interactive confirmation hook: return the basename to apply, or None to skip the file."""

ProgressFactory = Callable[[int], AbstractContextManager[ProgressCallback]]
"""Build a context-managed progress callback for a run over the given number of files."""


@dataclass(frozen=True)
class RenameHooks:
    """Optional interface hooks for one batch run; without them the run does no terminal I/O."""

    confirm: ConfirmCallback | None = None
    progress: ProgressFactory | None = None


@dataclass(frozen=True)
class RenameRunSummary:
    """Counters for one completed rename run."""

    processed: int
    renamed: int
    skipped: int
    failed: int


@dataclass(frozen=True)
class RenameRunResult:
    """Outcome of one batch run; summary is None when no files matched."""

    renamed_targets: set[Path]
    summary: RenameRunSummary | None = None


@dataclass
class _RenameRunState(RenameOutputData):
    """Mutable output state and resolved targets accumulated during one rename run."""

    renamed_targets: set[Path] = field(default_factory=set)
    confirm: ConfirmCallback | None = None
    warned_missing_confirm: bool = False


def _record_processing_exception(file_path: Path, exc: BaseException, state: _RenameRunState) -> None:
    """Classify an exception as fatal data failure, skipped no-text input, or recorded file failure."""
    if isinstance(exc, json.JSONDecodeError | DataFileError):
        raise exc
    if isinstance(exc, NoTextExtractedError):
        logger.warning("Skipping %s: %s", file_path.name, exc)
        state.skipped_count += 1
        return
    logger.exception("Failed to process %s: %s", file_path, exc)
    state.failed_count += 1
    state.failure_details.append({"file": str(file_path), "error": str(exc)})


def _confirm_rename(
    file_path: Path,
    new_base: str,
    meta: dict[str, object],
    config: RenamerConfig,
    state: _RenameRunState,
) -> tuple[bool, str]:
    """Ask the supplied confirm hook in interactive mode and return whether to apply the basename."""
    if not config.output.mode.interactive:
        return (True, new_base)
    if state.confirm is None:
        if not state.warned_missing_confirm:
            logger.warning("Interactive mode requires a confirm hook; skipping files without confirmation.")
            state.warned_missing_confirm = True
        return (False, new_base)
    chosen = state.confirm(file_path, new_base, meta)
    return (chosen is not None, chosen if chosen is not None else new_base)


def _apply_rename_result(
    file_path: Path,
    base: str,
    meta: dict[str, object],
    config: RenamerConfig,
    state: _RenameRunState,
) -> None:
    """Apply one suggestion and update output rows, counters, and resolved targets."""
    _on_rename_success = make_post_rename_success_callback(config, meta, state.export_rows)
    rows_before = len(state.export_rows)
    success, target = apply_single_rename(
        file_path,
        base,
        RenameApplyOptions(
            plan_file_path=config.output.paths.plan_file_path,
            plan_entries=state.plan_entries,
            dry_run=config.output.mode.dry_run,
            backup_dir=config.output.paths.backup_dir,
            on_success=_on_rename_success,
            max_filename_chars=config.output.naming.max_filename_chars,
        ),
    )
    if not success:
        logger.error("Skipping %s: could not rename after %s attempts", file_path.name, MAX_RENAME_RETRIES)
        state.failed_count += 1
        state.failure_details.append(
            {
                "file": str(file_path),
                "error": f"Could not rename after {MAX_RENAME_RETRIES} attempts.",
            }
        )
        return
    if config.output.mode.dry_run:
        if config.output.paths.export_metadata_path and len(state.export_rows) == rows_before:
            append_export_row(state.export_rows, file_path=file_path, target=target, meta=meta)
        logger.info("Dry-run: would rename '%s' to '%s'", file_path.name, target.name)
    else:
        logger.info("Renamed '%s' to '%s'", file_path.name, target.name)
        if target != file_path:
            state.renamed_targets.add(target.resolve())
    state.renamed_count += 1


def _handle_rename_result(
    proposal: Proposal,
    config: RenamerConfig,
    state: _RenameRunState,
) -> None:
    """Classify one produced result as a failure, skip, rejection, or applied rename."""
    file_path = proposal.source
    new_base = proposal.proposed_base
    meta = proposal.metadata
    exc = proposal.error
    state.processed_count += 1
    if exc is not None:
        _record_processing_exception(file_path, exc, state)
        return
    if new_base is None:
        logger.info("PDF content is empty. Skipping %s.", file_path.name)
        state.skipped_count += 1
        return
    should_apply, base = _confirm_rename(file_path, new_base, meta or {}, config, state)
    if not should_apply:
        state.skipped_count += 1
        return
    try:
        _apply_rename_result(file_path, base, meta or {}, config, state)
    except _RECOVERABLE_RENAME_EXCEPTIONS as rename_error:
        logger.exception("Failed to process %s: %s", file_path, rename_error)
        state.failed_count += 1
        state.failure_details.append({"file": str(file_path), "error": str(rename_error)})


def _produce_results_with_progress(
    files: list[Path],
    config: RenamerConfig,
    rules: ProcessingRules | None,
    progress: ProgressFactory | None,
) -> list[Proposal]:
    """Produce results with optional progress while retaining deterministic result ordering."""
    with progress(len(files)) if progress is not None else nullcontext() as callback:
        return produce_proposals(files, config, rules=rules, progress_callback=callback)


def rename_pdfs_in_directory(
    directory: str | Path,
    *,
    config: RenamerConfig,
    files_override: list[Path] | None = None,
    rules_override: ProcessingRules | None = None,
    hooks: RenameHooks | None = None,
) -> RenameRunResult:
    """Rename all PDFs in a directory using the configured pipeline (extract, LLM/heuristic, rename).

    Write export metadata, plan file, and summary JSON after processing. Use files_override to
    process specific files instead of scanning the directory. This layer does no terminal I/O:
    interactive mode requires a confirm hook (files are skipped without one), progress is reported
    through the optional progress factory (both supplied via hooks), and the caller renders the returned summary.
    """
    path, rules, files = _prepare_rename_run(
        directory,
        config,
        files_override=files_override,
        rules_override=rules_override,
    )
    if not files:
        _handle_empty_rename_run(path, config)
        return RenameRunResult(set())
    _log_rename_mode(config)
    active_hooks = hooks if hooks is not None else RenameHooks()
    state = _RenameRunState(confirm=active_hooks.confirm)
    results = _produce_results_with_progress(files, config, rules, active_hooks.progress)
    _apply_rename_results(results, files, config, state)
    _write_final_rename_outputs(config, path, state)
    return RenameRunResult(
        state.renamed_targets,
        RenameRunSummary(
            processed=state.processed_count,
            renamed=state.renamed_count,
            skipped=state.skipped_count,
            failed=state.failed_count,
        ),
    )


def _prepare_rename_run(
    directory: str | Path,
    config: RenamerConfig,
    *,
    files_override: list[Path] | None,
    rules_override: ProcessingRules | None,
) -> tuple[Path, ProcessingRules | None, list[Path]]:
    """Resolve the directory and rules, then collect PDF candidates for the run."""
    path = resolve_rename_directory(directory, files_override=files_override)
    rules = load_effective_rules(config, rules_override)
    files = collect_sorted_pdf_files(path, config, files_override=files_override, rules=rules)
    return (path, rules, files)


def _handle_empty_rename_run(path: Path, config: RenamerConfig) -> None:
    """Log an empty selection and emit an all-zero summary when configured."""
    logger.info("No matching PDF files found in %s", path)
    write_summary_json(
        config.output.paths.summary_json_path,
        RenameSummaryData(
            directory=path,
            processed=0,
            renamed=0,
            skipped=0,
            failed=0,
            dry_run=bool(config.output.mode.dry_run),
            failures=[],
        ),
    )


def _log_rename_mode(config: RenamerConfig) -> None:
    """Log heuristic-only mode and its missing summary and keyword fields."""
    if not config.llm.runtime.use_llm:
        logger.info("Heuristic-only mode (LLM disabled). Category from heuristics; summary and keywords will be empty.")


def _apply_rename_results(
    results: list[Proposal],
    files: list[Path],
    config: RenamerConfig,
    state: _RenameRunState,
) -> None:
    """Apply suggestions in order until stop is requested, updating run state."""
    for i, proposal in enumerate(results):
        if stop_requested(config):
            logger.info("Stop requested. Ending rename/apply phase.")
            break
        logger.info("Processing %s/%s: %s", i + 1, len(files), proposal.source)
        _handle_rename_result(proposal, config, state)


def _write_final_rename_outputs(config: RenamerConfig, path: Path, state: _RenameRunState) -> None:
    """Serialize accumulated export, plan, and summary files."""
    write_rename_outputs(
        config,
        path,
        RenameOutputData(
            export_rows=state.export_rows,
            plan_entries=state.plan_entries,
            processed_count=state.processed_count,
            renamed_count=state.renamed_count,
            skipped_count=state.skipped_count,
            failed_count=state.failed_count,
            failure_details=state.failure_details,
        ),
    )
