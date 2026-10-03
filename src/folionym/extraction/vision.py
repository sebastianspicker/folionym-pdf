"""Vision-model prompt for naming scanned documents from their first page."""

from __future__ import annotations

_VISION_FILENAME_TEMPLATE = (
    "{intro} {language_line}\n"
    "- 3–6 words, underscores only (no spaces), no special characters except _ and -.\n"
    "- {date_hint}\n"
    "- {uppercase_hint}\n"
    "{example_label}{example}\n\n"
    "{closing}"
)

_VISION_PROMPT_STRINGS: dict[str, dict[str, str]] = {
    "de": {
        "intro": "Erzeuge einen kurzen Dateinamen (ohne Endung) für dieses gescannte Dokument.",
        "language_line": "In Deutsch.",
        "date_hint": "Optional: Datum am Ende (z. B. 2023-11-15).",
        "uppercase_hint": "Großschreibung bevorzugt.",
        "example_label": "Beispiel: ",
        "example": "RECHNUNG_AMAZON_MAX_2023-11-15",
        "closing": "Antworte mit NUR dem Dateinamen, sonst nichts.",
    },
    "en": {
        "intro": "Generate a short filename (without extension) for this scanned document.",
        "language_line": "In English.",
        "date_hint": "Optional: date at end (e.g. 2023-11-15).",
        "uppercase_hint": "Uppercase preferred.",
        "example_label": "Example: ",
        "example": "INVOICE_AMAZON_JOHN_2023-11-15",
        "closing": "Respond with ONLY the filename, nothing else.",
    },
}


def _language_code(language: str) -> str:
    """Normalize prompt language to a supported dictionary key."""
    normalized = language.strip().lower()
    primary = normalized.replace("_", "-").split("-", 1)[0]
    return "de" if primary == "de" else "en"


def build_vision_filename_prompt(language: str) -> str:
    """Build Montscan-style strict prompt for vision API: filename only, 3–6 words, underscores, optional date."""
    return _VISION_FILENAME_TEMPLATE.format(**_VISION_PROMPT_STRINGS[_language_code(language)])
