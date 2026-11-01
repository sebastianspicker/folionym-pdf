"""Pure filename-safety policy shared by naming, LLM, extraction, and rename code."""

from __future__ import annotations

import re
import unicodedata

# Path separators and control characters (including NUL) must not appear in names.
FILENAME_UNSAFE_RE = re.compile(r"[\x00-\x1f\x7f/\\:*?\"<>|]")
FILENAME_RESERVED_WIN = frozenset(
    {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
)
MAX_LLM_FILENAME_LEN = 120


def sanitize_filename_base(name: str) -> str:
    """Remove unsafe characters, empty names, and Windows device names."""
    if not name or not name.strip():
        return "unnamed"
    safe = FILENAME_UNSAFE_RE.sub("", _visible_text(name).strip()).strip() or "unnamed"
    return f"{safe}_" if safe.upper() in FILENAME_RESERVED_WIN else safe


# Controls (C0 and C1), lone surrogates, line/paragraph separators and invisible format marks
# (bidi overrides, zero-width spaces, BOM) can hide or reorder what a name shows.
_HIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
# Zero-width non-joiner and joiner shape Persian and Indic words, so they stay.
_KEPT_FORMAT_CHARACTERS = frozenset({chr(0x200C), chr(0x200D)})


def _visible_text(name: str) -> str:
    """Drop hidden characters and turn every kind of space into a plain space."""
    kept: list[str] = []
    for character in name:
        category = unicodedata.category(character)
        if category == "Zs":
            kept.append(" ")
        elif category not in _HIDDEN_CATEGORIES or character in _KEPT_FORMAT_CHARACTERS:
            kept.append(character)
    return "".join(kept)


def sanitize_filename_from_llm(raw: str) -> str:
    """Sanitize LLM or vision output for use as a filename component."""
    if not raw or not isinstance(raw, str):
        return "document"
    cleaned = raw.strip()
    for character in '/\\:*?"<>|':
        cleaned = cleaned.replace(character, "_")
    cleaned = "_".join(" ".join(cleaned.replace("\n", " ").replace("\r", " ").split()).split(" "))
    if cleaned.lower().endswith(".pdf"):
        cleaned = cleaned[:-4]
    cleaned = cleaned.strip("._") or "document"
    return cleaned[:MAX_LLM_FILENAME_LEN]
