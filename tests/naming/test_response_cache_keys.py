"""Pinned response-cache keys so existing on-disk caches keep hitting across refactors."""

from __future__ import annotations

from folionym.naming.analysis import AnalysisOptions, get_document_analysis
from folionym.naming.simple_filename import SimpleFilenameOptions, get_document_filename_simple

_DOCUMENT = "Rechnung Nr. INV-2025-0042 der Muster GmbH über 249,90 EUR vom 15.03.2025."

# Recorded from the pre-refactor implementation (folionym.llm.service / folionym.llm.simple).
_ANALYSIS_KEY = "52ad3e84a6aebec82000f0791c2d7df7c2302d66e7ce7f7ae0eacb05d81fb165"
_SIMPLE_FILENAME_KEY = "55895ae3f20190175a94bf5fe658597865528c8970791afe7d432fc0d1e1b15c"


class _RecordingCache:
    """Response-cache stand-in that records every looked-up key and always misses."""

    def __init__(self) -> None:
        self.keys: list[str] = []

    def get(self, key: str) -> str | None:
        self.keys.append(key)
        return None

    def set(self, key: str, value: str) -> None:
        return None


class _FixedClient:
    model = "pinned-model"
    base_url = ""

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> str:
        return '{"summary":"Rechnung","keywords":["Rechnung"],"category":"invoice"}'


def test_analysis_response_cache_key_is_stable() -> None:
    cache = _RecordingCache()

    get_document_analysis(
        _FixedClient(),
        _DOCUMENT,
        AnalysisOptions(language="de", cache=cache, cache_key_base="file-key"),
    )

    assert cache.keys == [_ANALYSIS_KEY]


def test_simple_filename_response_cache_key_is_stable() -> None:
    cache = _RecordingCache()

    get_document_filename_simple(
        _FixedClient(),
        _DOCUMENT,
        SimpleFilenameOptions(language="de", cache=cache, cache_key_base="file-key"),
    )

    assert cache.keys == [_SIMPLE_FILENAME_KEY]
