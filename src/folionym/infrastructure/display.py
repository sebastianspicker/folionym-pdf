"""Render untrusted local strings as inert terminal text."""

from __future__ import annotations

_NAMED_ESCAPES = {
    "\0": r"\0",
    "\a": r"\a",
    "\b": r"\b",
    "\t": r"\t",
    "\n": r"\n",
    "\v": r"\v",
    "\f": r"\f",
    "\r": r"\r",
}
_BIDI_CONTROLS = frozenset(
    {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)


def escape_terminal_text(value: object) -> str:
    """Escape terminal and bidirectional controls while preserving ordinary Unicode."""
    escaped: list[str] = []
    for character in str(value):
        if character in _NAMED_ESCAPES:
            escaped.append(_NAMED_ESCAPES[character])
            continue
        codepoint = ord(character)
        if codepoint < 32 or 127 <= codepoint <= 159:
            escaped.append(f"\\x{codepoint:02x}")
        elif character in _BIDI_CONTROLS:
            escaped.append(f"\\u{codepoint:04x}")
        else:
            escaped.append(character)
    return "".join(escaped)
