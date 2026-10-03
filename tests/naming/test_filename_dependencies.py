"""Filename-generation dependency resolution only touches the response cache when an LLM is enabled."""

from __future__ import annotations

from pathlib import Path

import pytest

from folionym.naming import service as naming_service
from folionym.naming.models import FilenameGenerationContext, FilenameGenerationRequest
from folionym.settings.models import LLMConfig, LLMRuntimeConfig, RenamerConfig


def test_disabled_llm_skips_cache_resolution_and_file_digest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"pdf")
    monkeypatch.setattr(
        naming_service,
        "resolve_response_cache",
        lambda *_args, **_kwargs: pytest.fail("disabled LLM must not initialize or hash for response caching"),
    )
    request = FilenameGenerationRequest(
        config=RenamerConfig(llm=LLMConfig(runtime=LLMRuntimeConfig(use_llm=False))),
        context=FilenameGenerationContext(source_path=source),
    )

    dependencies = naming_service.resolve_filename_dependencies(request)

    assert dependencies.cache.response_cache is None
    assert dependencies.cache.cache_key_base is None
