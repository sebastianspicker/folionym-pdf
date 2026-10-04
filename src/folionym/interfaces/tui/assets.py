"""Constants and CSS for the Rich/Textual TUI."""

from __future__ import annotations

from textual.theme import Theme

from ...settings import DATE_LOCALE_CHOICES, DESIRED_CASE_CHOICES, LANGUAGE_CHOICES, WORKFLOW_PRESET_CHOICES

PREVIEW_COLOR = "#2468E5"
SUCCESS_COLOR = "#087F70"
WARNING_COLOR = "#A45D00"
ERROR_COLOR = "#B42318"

_LANGUAGE_LABELS = {"de": "German (de)", "en": "English (en)"}
_DATE_FORMAT_LABELS = {"dmy": "Day-Month-Year (dmy)", "mdy": "Month-Day-Year (mdy)"}
LANGUAGE_OPTIONS = [(_LANGUAGE_LABELS[code], code) for code in LANGUAGE_CHOICES]
CASE_OPTIONS = [(case, case) for case in DESIRED_CASE_CHOICES]
DATE_FORMAT_OPTIONS = [(_DATE_FORMAT_LABELS[code], code) for code in DATE_LOCALE_CHOICES]
PRESET_OPTIONS = [("(none)", ""), *((preset, preset) for preset in WORKFLOW_PRESET_CHOICES)]

FOLIONYM_THEME = Theme(
    name="folionym-ledger",
    primary=PREVIEW_COLOR,
    secondary="#647082",
    accent=PREVIEW_COLOR,
    foreground="#17202D",
    background="#FBFCFE",
    surface="#F2F5FA",
    panel="#E9EFF8",
    boost="#E0E6EF",
    success=SUCCESS_COLOR,
    warning=WARNING_COLOR,
    error=ERROR_COLOR,
    dark=False,
    variables={
        "muted-copy": "#566273",
        "quiet-border": "#D6DDE7",
        "strong-border": "#B7C0CE",
        "selection-soft": "#E7F0FF",
        "success-soft": "#E5F5F1",
        "warning-soft": "#FFF2D6",
        "error-soft": "#FDECEA",
    },
)
