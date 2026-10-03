"""Framework-free single-file rename operation for the Textual controller."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rich.markup import escape as escape_markup

from ...application.single_file import rename_single_file
from ...settings import RenamerConfig
from .assets import ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR

_SKIP = f"[{WARNING_COLOR}]SKIP[/{WARNING_COLOR}]"
_ERR = f"[{ERROR_COLOR}]ERR[/{ERROR_COLOR}] "


@dataclass(frozen=True)
class SingleFileOperationResult:
    """Worker-ready logs and terminal state for one suggested rename."""

    log_lines: tuple[str, ...]
    ok: bool
    message: str
    outcome: Literal["renamed", "skipped", "failed"]


def process_single_file(fp: Path, config: RenamerConfig) -> SingleFileOperationResult:
    """Suggest and apply one rename while returning UI-neutral output events."""
    outcome = rename_single_file(fp, config)
    if outcome.error is not None:
        return SingleFileOperationResult(
            (f"{_ERR} [bold {ERROR_COLOR}]Error: {escape_markup(str(outcome.error))}[/bold {ERROR_COLOR}]\n",),
            False,
            str(outcome.error),
            "failed",
        )
    if outcome.base is None or outcome.target is None:
        return SingleFileOperationResult(
            (f"{_SKIP} [dim]Skipped -- no extractable content.[/dim]\n",), True, "Skipped", "skipped"
        )
    metadata = outcome.metadata
    target = outcome.target
    suggested = outcome.base + fp.suffix
    if not outcome.success:
        return SingleFileOperationResult(
            (
                f"[dim]Suggested:[/dim] [bold]{escape_markup(suggested)}[/bold]\n",
                f"{_ERR} [bold {ERROR_COLOR}]Could not rename file.[/bold {ERROR_COLOR}]\n",
            ),
            False,
            "Could not rename file",
            "failed",
        )
    rename_line = (
        f"[{SUCCESS_COLOR}]Renamed[/{SUCCESS_COLOR}] [dim]{escape_markup(fp.name)}[/dim]"
        f" [{SUCCESS_COLOR} bold]->[/{SUCCESS_COLOR} bold] [bold]{escape_markup(target.name)}[/bold]\n"
    )
    metadata_line = _format_metadata(metadata)
    lines = [f"[dim]Suggested:[/dim] [bold]{escape_markup(suggested)}[/bold]\n", rename_line]
    if metadata_line:
        lines.append(metadata_line)
    return SingleFileOperationResult(tuple(lines), True, "Completed", "renamed")


def _format_metadata(meta: dict[str, object]) -> str | None:
    """Format inspectable metadata with the exact established field order."""
    parts = [
        f"[dim]{key}:[/dim] {escape_markup(str(value))}"
        for key in ("category", "summary", "keywords", "category_source")
        if (value := meta.get(key))
    ]
    return "  " + "  |  ".join(parts) + "\n" if parts else None
