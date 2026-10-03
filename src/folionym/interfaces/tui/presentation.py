"""Framework-free parsing and presentation for the terminal run view."""

from __future__ import annotations

from collections.abc import Callable

from ...application.privacy import external_llm_endpoint, run_contacts_model
from ...settings import RenamerConfig
from .assets import (
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
)

RunCounts = dict[str, int]


def snapshot_from_readers(
    get_str: Callable[[str, str], str],
    get_bool: Callable[[str, bool], bool],
    get_select: Callable[[str, str], str],
) -> dict[str, object]:
    """Collect the persisted configuration shape from caller-supplied widget readers."""
    return {
        "directory": get_str("directory", ""),
        "single_file": get_str("single_file", ""),
        "language": get_select("language", "de"),
        "case": get_select("case", "kebabCase"),
        "date_format": get_select("date_format", "dmy"),
        "preset": get_select("preset", ""),
        "project": get_str("project", ""),
        "version": get_str("version", ""),
        "template": get_str("template", ""),
        "backup_dir": get_str("backup_dir", ""),
        "rename_log": get_str("rename_log", ""),
        "export_metadata": get_str("export_metadata", ""),
        "summary_json": get_str("summary_json", ""),
        "rules_file": get_str("rules_file", ""),
        "post_rename_hook": get_str("post_rename_hook", ""),
        "llm_url": get_str("llm_url", ""),
        "llm_model": get_str("llm_model", ""),
        "llm_timeout": get_str("llm_timeout", ""),
        "max_tokens": get_str("max_tokens", ""),
        "max_content_chars": get_str("max_content_chars", ""),
        "max_content_tokens": get_str("max_content_tokens", ""),
        "workers": get_str("workers", ""),
        "max_filename_chars": get_str("max_filename_chars", ""),
        "dry_run": True,
        "use_llm": get_bool("use_llm", True),
        "use_ocr": get_bool("use_ocr", False),
        "recursive": get_bool("recursive", False),
        "skip_already_named": get_bool("skip_already_named", False),
        "use_pdf_metadata_date": get_bool("use_pdf_metadata_date", True),
        "use_structured_fields": get_bool("use_structured_fields", True),
        "write_pdf_metadata": get_bool("write_pdf_metadata", False),
        "use_vision_fallback": get_bool("use_vision_fallback", False),
        "simple_naming_mode": get_bool("simple_naming_mode", False),
        "vision_first": get_bool("vision_first", False),
    }


def endpoint_disclosure(config: RenamerConfig | None) -> tuple[str, str]:
    """Describe the content boundary of the run *config* would perform, without exposing endpoint details.

    ``None`` stands for a form that does not yet build a valid configuration.
    """
    if config is None:
        return "HTTP MODEL", "Review the endpoint before sending document-derived content."
    if not run_contacts_model(config):
        return "HEURISTICS ONLY", "Document text stays on this machine."
    try:
        external = external_llm_endpoint(config)
    except ValueError:
        return "HTTP MODEL", "Review the endpoint before sending document-derived content."
    if external is None:
        return "LOCAL HTTP MODEL", "Document text may be sent to the configured local endpoint."
    return "EXTERNAL HTTP MODEL", "Document-derived content may leave this machine."


def effective_configuration_lines(language: str, case_style: str, preset: str, ocr_enabled: bool) -> str:
    """Format the concise control summary used by the next-run disclosure."""
    return "\n".join(
        (
            f"LANGUAGE       {language.upper()}",
            f"FILENAME STYLE {case_style}",
            f"PRESET         {preset or 'custom'}",
            f"OCR            {'enabled' if ocr_enabled else 'off'}",
        )
    )


def format_run_summary(counts: RunCounts, preview: bool, *, separator: str) -> str:
    """Format colored counters for the run view or terminal completion line."""
    result_label = "suggestions" if preview else "renamed"
    parts = []
    if counts["renamed"]:
        parts.append(f"[{SUCCESS_COLOR}]{counts['renamed']} {result_label}[/{SUCCESS_COLOR}]")
    if counts["skipped"]:
        parts.append(f"[{WARNING_COLOR}]{counts['skipped']} skipped[/{WARNING_COLOR}]")
    if counts["failed"]:
        parts.append(f"[{ERROR_COLOR}]{counts['failed']} failed[/{ERROR_COLOR}]")
    return separator.join(parts)


def metric_summary(counts: RunCounts, preview: bool) -> tuple[str, str, str]:
    """Format the three persistent run metrics without duplicating their labels."""
    result_label = "suggestions" if preview else "renamed"
    return (
        f"[b]{counts['renamed']}[/b] {result_label}",
        f"[b]{counts['skipped']}[/b] skipped",
        f"[b]{counts['failed']}[/b] failed",
    )


def completion_summary(counts: RunCounts, preview: bool) -> str:
    """Return the final completion copy, including the established empty-run fallback."""
    return format_run_summary(counts, preview, separator="  ") or "no files processed"
