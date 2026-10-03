"""Terminal adapter for the conventional CLI workflows.

The application layer performs no terminal I/O. This module supplies the
interactive confirm/edit prompt, manual-mode suggestions, Rich progress, and the
run summary, and wraps the batch and watch workflows with them. Both the CLI and
the public ``folionym.renamer`` facade use it so their output is identical.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, ProgressColumn, TextColumn, TimeElapsedColumn

from ...application.batch import (
    ConfirmCallback,
    ProgressFactory,
    RenameHooks,
    RenameRunResult,
    RenameRunSummary,
    rename_pdfs_in_directory,
)
from ...application.proposals import ProgressCallback
from ...application.watch import WatchHooks, run_watch_loop
from ...infrastructure.filenames import sanitize_filename_base
from ...naming.rules import ProcessingRules
from ...settings import RenamerConfig

__all__ = [
    "make_confirm",
    "make_progress",
    "print_run_summary",
    "rename_with_terminal",
    "watch_with_terminal",
]

_MANUAL_META_KEYS = ("category", "summary", "keywords", "category_source")


def _edit_prompt_text(edit_default_base: str | None) -> str:
    """Build the edit prompt with an optional default basename."""
    default = f" [default: {edit_default_base}]" if edit_default_base else ""
    return f"New filename (without path){default}: "


def _strip_pdf_suffix(value: str, suffix: str) -> str:
    """Remove a matching PDF suffix case-insensitively."""
    return value[: -len(suffix)] if suffix and value.lower().endswith(suffix.lower()) else value


def _interactive_rename_prompt(
    file_path: Path, target: Path, default_base: str, edit_default_base: str | None = None
) -> tuple[str, str]:
    """Prompt for y/n/e=edit and return the selected action and basename."""
    current_base = default_base
    current_target = target
    while True:
        try:
            prompt = f"Rename '{file_path.name}' to '{current_target.name}'? (y/n/e=edit, default y): "
            reply = input(prompt).strip().lower() or "y"
        except EOFError, KeyboardInterrupt:
            return ("n", current_base)
        if reply == "n":
            return ("n", current_base)
        if reply != "e":
            return ("y", current_base)
        try:
            edited = input(_edit_prompt_text(edit_default_base)).strip()
        except EOFError, KeyboardInterrupt:
            continue
        edited = edited or edit_default_base or ""
        if not edited:
            continue
        current_base = sanitize_filename_base(_strip_pdf_suffix(edited, file_path.suffix))
        return ("y", current_base)


def make_confirm(config: RenamerConfig) -> ConfirmCallback:
    """Build the terminal confirm hook honoring the manual-mode setting of the config."""
    manual_mode = config.output.mode.manual_mode

    def confirm(file_path: Path, new_base: str, meta: dict[str, object]) -> str | None:
        target = file_path.with_name(new_base + file_path.suffix)
        if manual_mode:
            print(f"Suggested: {new_base}{file_path.suffix}")
            for key, value in meta.items():
                if key in _MANUAL_META_KEYS and value:
                    print(f"  {key}: {value}")
        reply, base = _interactive_rename_prompt(
            file_path, target, new_base, edit_default_base=new_base if manual_mode else None
        )
        return None if reply == "n" else base

    return confirm


def make_progress(config: RenamerConfig) -> ProgressFactory | None:
    """Build the Rich stderr progress factory, or None when progress output is disabled."""
    options = config.output.progress_options
    if not (options.progress or options.quiet_progress):
        return None

    @contextmanager
    def progress_for(total: int) -> Iterator[ProgressCallback]:
        columns: list[ProgressColumn] = [TextColumn("{task.completed}/{task.total}")]
        if not options.quiet_progress:
            columns.append(BarColumn(bar_width=None))
        columns.extend(
            [
                TextColumn("{task.percentage:>3.0f}%"),
                TextColumn("{task.fields[filename]}"),
                TimeElapsedColumn(),
            ]
        )
        progress = Progress(*columns, console=Console(stderr=True), transient=True)
        task_id = progress.add_task("Processing PDFs", total=total, filename="")

        def update(current: int, total: int, file_path: Path) -> None:
            progress.update(task_id, total=total, completed=current, filename=file_path.name)

        progress.start()
        try:
            yield update
        finally:
            progress.stop()

    return progress_for


def print_run_summary(summary: RenameRunSummary) -> None:
    """Print a colorized run summary to stderr with Rich."""
    con = Console(stderr=True)
    con.print()
    parts = [f"[bold]{summary.processed}[/bold] processed"]
    if summary.renamed:
        parts.append(f"[green]{summary.renamed} renamed[/green]")
    else:
        parts.append(f"{summary.renamed} renamed")
    if summary.skipped:
        parts.append(f"[yellow]{summary.skipped} skipped[/yellow]")
    else:
        parts.append(f"{summary.skipped} skipped")
    if summary.failed:
        parts.append(f"[red]{summary.failed} failed[/red]")
    else:
        parts.append(f"{summary.failed} failed")
    con.print("[bold]Summary:[/bold] " + ", ".join(parts))


def rename_with_terminal(
    directory: str | Path,
    *,
    config: RenamerConfig,
    files_override: list[Path] | None = None,
    rules_override: ProcessingRules | None = None,
) -> RenameRunResult:
    """Run one batch rename with terminal prompts and progress, then print the run summary."""
    result = rename_pdfs_in_directory(
        directory,
        config=config,
        files_override=files_override,
        rules_override=rules_override,
        hooks=RenameHooks(confirm=make_confirm(config), progress=make_progress(config)),
    )
    if result.summary is not None:
        print_run_summary(result.summary)
    return result


def watch_with_terminal(directory: str | Path, *, config: RenamerConfig, interval_seconds: float = 60.0) -> None:
    """Run the watch loop with terminal prompts, progress, and per-run summaries."""
    run_watch_loop(
        directory,
        config=config,
        interval_seconds=interval_seconds,
        hooks=WatchHooks(
            rename=RenameHooks(confirm=make_confirm(config), progress=make_progress(config)),
            on_summary=print_run_summary,
        ),
    )
