"""LLM JSON parsing recovers the permitted shapes and never logs document content."""

from __future__ import annotations

import pytest

from folionym.llm.parsing import extract_and_validate_json, parse_json_field


def test_llm_json_parser_recovers_permitted_shapes_without_logging_document_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_text = "PRIVATE_PDF_SNIPPET_1234567890"
    assert parse_json_field('```json\n{"summary":"invoice"}\n```', key="summary") == "invoice"
    assert parse_json_field('"keywords":[" invoice ","2026"]', key="keywords", lenient=True) == [
        "invoice",
        "2026",
    ]
    assert extract_and_validate_json(
        'prefix "keywords":[" invoice ", "2026"]',
        expected_keys={"keywords"},
        lenient_keys={"keywords"},
    ) == {"keywords": ["invoice", "2026"]}
    assert extract_and_validate_json(
        'prefix "summary":"fallback"',
        expected_keys={"summary"},
        lenient_keys={"summary"},
    ) == {"summary": "fallback"}

    assert parse_json_field(f"not json {private_text}", key="summary") is None
    assert private_text not in caplog.text
