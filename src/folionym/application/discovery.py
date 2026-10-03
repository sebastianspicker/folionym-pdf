"""Directory, rules, and PDF discovery helpers for the batch renamer."""

from __future__ import annotations

import fnmatch
import logging
import os
import re
import string
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from ..infrastructure.files import is_path_within, open_directory_no_follow
from ..naming.rules import ProcessingRules, load_processing_rules, should_skip_file_by_rules
from ..settings import RenamerConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PdfCollectionOptions:
    """Options controlling PDF discovery and post-discovery filtering."""

    recursive: bool = False
    max_depth: int = 0
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None
    skip_if_already_named: bool = False
    files_override: list[Path] | None = None
    rules: ProcessingRules | None = None


def _matches_patterns(name: str, include: list[str] | None, exclude: list[str] | None) -> bool:
    name_lower = name.lower()
    if include and not any(fnmatch.fnmatchcase(name_lower, pattern.lower()) for pattern in include):
        return False
    return not (exclude and any(fnmatch.fnmatchcase(name_lower, pattern.lower()) for pattern in exclude))


def _scan_pdf_candidates(directory: Path, opts: PdfCollectionOptions) -> Iterator[Path]:
    """Prune depth before descending and use DirEntry's cached file-type metadata."""
    pending = [(directory, 0)]
    while pending:
        folder, depth = pending.pop()
        children: list[tuple[Path, int]] = []
        directory_fd: int | None = None
        try:
            directory_fd = open_directory_no_follow(folder)
            scan_target: int | Path = directory_fd if os.name != "nt" else folder
            with os.scandir(scan_target) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    path = folder / entry.name
                    if entry.is_dir(follow_symlinks=False):
                        if opts.recursive and (opts.max_depth <= 0 or depth < opts.max_depth):
                            children.append((path, depth + 1))
                    elif (
                        not entry.name.startswith(".")
                        and path.suffix.lower() == ".pdf"
                        and entry.is_file(follow_symlinks=False)
                    ):
                        yield path
        except OSError:
            if not opts.recursive:
                raise
        finally:
            if directory_fd is not None:
                os.close(directory_fd)
        pending.extend(reversed(children))


def _collect_override_candidates(directory: Path, files_override: list[Path]) -> list[Path]:
    candidates = [
        path
        for path in files_override
        if path.is_file()
        and path.suffix.lower() == ".pdf"
        and not path.is_symlink()
        and is_path_within(path, directory)
    ]
    if len(candidates) != len([path for path in files_override if path.suffix.lower() == ".pdf"]):
        logger.warning("Ignoring files_override PDFs outside selected directory or symbolic links in %s", directory)
    return candidates


def collect_pdf_files(directory: Path, options: PdfCollectionOptions | None = None) -> list[Path]:
    """Collect configured visible PDFs, rejecting source symlinks and applying filters."""
    opts = options or PdfCollectionOptions()
    if opts.files_override is not None:
        candidates: list[Path] | Iterator[Path] = _collect_override_candidates(directory, opts.files_override)
    else:
        candidates = _scan_pdf_candidates(directory, opts)
    already_named = re.compile(r"^\d{8}-.+\.[pP][dD][fF]$") if opts.skip_if_already_named else None
    return [
        path
        for path in candidates
        if _matches_patterns(path.name, opts.include_patterns, opts.exclude_patterns)
        and (opts.rules is None or not should_skip_file_by_rules(opts.rules, path.name))
        and (already_named is None or not already_named.match(path.name))
    ]


def resolve_rename_directory(directory: str | Path, *, files_override: list[Path] | None) -> Path:
    """Validate and resolve the selected path, permitting a non-directory only with file overrides."""
    dir_str = str(directory).strip()
    if not dir_str:
        raise ValueError("Directory path must be non-empty. Use --dir or provide when prompted.")
    path = Path(directory)
    if not path.exists():
        raise FileNotFoundError(f"Directory does not exist: {path}")
    if files_override is None and not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")
    return path.resolve()


def load_effective_rules(config: RenamerConfig, rules_override: ProcessingRules | None) -> ProcessingRules | None:
    """Use the supplied rules override or load the configured rules file."""
    if rules_override is not None:
        return rules_override
    rules_file = config.output.paths.rules_file
    return load_processing_rules(rules_file, raise_on_error=bool(rules_file))


def _mtime_key(path: Path) -> float:
    """Return modification time for sorting, using zero when stat fails."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def collect_configured_pdf_files(
    path: Path,
    config: RenamerConfig,
    *,
    files_override: list[Path] | None,
    rules: ProcessingRules | None,
) -> list[Path]:
    """Translate traversal configuration into collection options and collect PDF candidates."""
    traversal = config.output.traversal
    return collect_pdf_files(
        path,
        PdfCollectionOptions(
            recursive=traversal.recursive,
            max_depth=traversal.max_depth,
            include_patterns=traversal.include_patterns,
            exclude_patterns=traversal.exclude_patterns,
            skip_if_already_named=config.output.mode.skip_if_already_named,
            files_override=files_override,
            rules=rules,
        ),
    )


def collect_sorted_pdf_files(
    path: Path,
    config: RenamerConfig,
    *,
    files_override: list[Path] | None,
    rules: ProcessingRules | None,
) -> list[Path]:
    """Collect configured PDF candidates and sort them by newest modification time."""
    files = collect_configured_pdf_files(path, config, files_override=files_override, rules=rules)
    files.sort(key=_mtime_key, reverse=True)
    return files


def count_directory_pdfs(directory: Path) -> int:
    """Count the PDFs a depth-one Preview of ``directory`` would discover, or zero when unreadable."""
    try:
        return sum(1 for _path in _scan_pdf_candidates(directory, PdfCollectionOptions()))
    except OSError:
        return 0


def list_child_directories(directory: Path) -> list[Path]:
    """List non-hidden, non-symlink child directories in a stable order.

    Raises ``PermissionError`` when ``directory`` cannot be read.
    """
    return sorted(
        (
            child
            for child in directory.iterdir()
            if child.is_dir() and not child.is_symlink() and not child.name.startswith(".")
        ),
        key=lambda child: child.name.casefold(),
    )


def local_filesystem_roots() -> list[Path]:
    """Return the resolved home directory and filesystem or drive roots that exist, without duplicates."""
    candidates: list[Path] = [Path.home()]
    if os.name == "nt":
        candidates.extend(Path(f"{letter}:\\") for letter in string.ascii_uppercase if Path(f"{letter}:\\").exists())
    else:
        candidates.append(Path("/"))
    unique: dict[Path, None] = {}
    for root in candidates:
        try:
            unique[root.resolve(strict=True)] = None
        except OSError:
            continue
    return list(unique)
