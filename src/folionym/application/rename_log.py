"""Tab-delimited rename log format shared by the rename writers and the undo use case.

One line per rename, 'old_path\tnew_path'. Filenames containing tab or newline characters
are not supported; such entries are skipped at write time with a WARNING. The renamer
sanitizes generated names so they never contain these characters.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..infrastructure.private_io import open_private_append_text

logger = logging.getLogger(__name__)


def append_rename_log_entry(rename_log_path: str | Path, file_path: Path, target: Path) -> None:
    """Append one private tab-delimited rename record with unambiguous path fields."""
    file_path_str = str(file_path)
    target_str = str(target)
    if any(delimiter in file_path_str for delimiter in ("\t", "\n", "\r")):
        logger.warning(
            "Cannot write rename log entry for %s: original path contains tab or newline "
            "characters (unsupported by the tab-delimited log format). Undo will not be "
            "available for this file.",
            file_path,
        )
        return
    if any(delimiter in target_str for delimiter in ("\t", "\n", "\r")):
        logger.warning(
            "Cannot write rename log entry for %s: target path contains tab or newline "
            "characters (unsupported by the tab-delimited log format). Undo will not be "
            "available for this file.",
            target,
        )
        return
    with open_private_append_text(rename_log_path) as handle:
        handle.write(f"{file_path_str}\t{target_str}\n")


def read_rename_log_pairs(log_path: Path) -> list[tuple[str, str]]:
    """Parse valid tab-separated rename pairs and return them in reverse order for LIFO undo."""
    pairs: list[tuple[str, str]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line == "" or line.isspace():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        old_path, new_path = parts
        if old_path and new_path:
            pairs.append((old_path, new_path))
    pairs.reverse()
    return pairs
