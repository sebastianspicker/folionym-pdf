"""Pin the outputs of the three filename sanitizers over tricky inputs."""

from __future__ import annotations

import pytest

from folionym.infrastructure.filenames import sanitize_filename_base, sanitize_filename_from_llm
from folionym.naming.tokens import clean_token

# input, clean_token, sanitize_filename_base, sanitize_filename_from_llm
CASES = [
    ("", "na", "unnamed", "document"),
    ("  ", "na", "unnamed", "document"),
    ("CON", "con_", "CON_", "CON"),
    ("con", "con_", "con_", "con"),
    ("Com1", "com1_", "Com1_", "Com1"),
    ("nul.", "nul_", "nul.", "nul"),
    ("a/b", "ab", "ab", "a_b"),
    ("a:b*c", "abc", "abc", "a_b_c"),
    ("...", "na", "...", "document"),
    ("a.b.", "a.b", "a.b.", "a.b"),
    ("Müller Straße", "mueller_strasse", "Müller Straße", "Müller_Straße"),
    ("ÄÖÜ ẞ", "aeoeue_ss", "ÄÖÜ ẞ", "ÄÖÜ_ẞ"),
    ("x\ty", "x_y", "xy", "x_y"),
    ("a\x00b", "a\x00b", "ab", "a\x00b"),
    ("  hi  there ", "hi_there", "hi  there", "hi_there"),
    ("Report.pdf", "report.pdf", "Report.pdf", "Report"),
]


@pytest.mark.parametrize(("raw", "token", "base", "llm"), CASES)
def test_sanitizer_outputs_are_pinned(raw: str, token: str, base: str, llm: str) -> None:
    assert clean_token(raw) == token
    assert sanitize_filename_base(raw) == base
    assert sanitize_filename_from_llm(raw) == llm
