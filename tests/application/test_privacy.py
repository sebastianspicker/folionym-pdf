"""Content-boundary decision shared by the browser and terminal interfaces."""

from __future__ import annotations

from dataclasses import replace

import pytest

from folionym.application.privacy import external_llm_endpoint
from folionym.settings import LLMBackendConfig, LLMConfig, RenamerConfig, build_config

_REMOTE_URL = "https://llm.remote.example/v1/completions"


@pytest.mark.parametrize(
    ("raw", "env"),
    [
        ({"use_llm": False, "llm_base_url": _REMOTE_URL}, {}),
        ({}, {}),
        ({"llm_base_url": "http://127.0.0.1:11434/api/generate"}, {}),
        ({"llm_base_url": "http://localhost:1234/v1/chat/completions", "vision_first": True}, {}),
        (
            {"use_llm": False},
            {"FOLIONYM_LLM_URL": "http://127.0.0.1:8080/v1/completions", "FOLIONYM_VISION_FIRST": "1"},
        ),
    ],
)
def test_disabled_preset_default_and_loopback_endpoints_are_not_external(
    raw: dict[str, object], env: dict[str, str]
) -> None:
    assert external_llm_endpoint(build_config(raw, env=env)) is None


@pytest.mark.parametrize(
    ("raw", "env"),
    [
        ({"llm_base_url": f" {_REMOTE_URL} "}, {}),
        ({"llm_base_url": ""}, {"FOLIONYM_LLM_URL": _REMOTE_URL}),
        ({"use_llm": False, "use_vision_fallback": True, "llm_base_url": _REMOTE_URL}, {}),
        ({"use_llm": False}, {"FOLIONYM_LLM_URL": _REMOTE_URL, "FOLIONYM_USE_VISION_FALLBACK": "1"}),
    ],
)
def test_the_resolved_non_loopback_endpoint_is_returned_normalized(raw: dict[str, object], env: dict[str, str]) -> None:
    assert external_llm_endpoint(build_config(raw, env=env)) == _REMOTE_URL


def test_library_configs_fall_back_to_the_environment_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOLIONYM_LLM_URL", _REMOTE_URL)
    assert external_llm_endpoint(RenamerConfig()) == _REMOTE_URL


def test_invalid_endpoint_raises_value_error() -> None:
    config = replace(RenamerConfig(), llm=LLMConfig(backend=LLMBackendConfig(llm_base_url="ftp://example.com")))
    with pytest.raises(ValueError):
        external_llm_endpoint(config)
