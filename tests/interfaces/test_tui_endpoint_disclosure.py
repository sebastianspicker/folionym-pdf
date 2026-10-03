"""The terminal content-boundary disclosure describes the endpoint the run will use."""

from __future__ import annotations

from threading import Event

import pytest

from folionym.interfaces.tui.presentation import endpoint_disclosure
from folionym.interfaces.ui_settings import build_config_from_ui_settings, merged_ui_settings

_REMOTE_URL = "https://llm.remote.example/v1/completions"


@pytest.fixture(autouse=True)
def _clear_model_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("FOLIONYM_LLM_URL", "FOLIONYM_USE_VISION_FALLBACK", "FOLIONYM_VISION_FIRST"):
        monkeypatch.delenv(name, raising=False)


def _disclosure(form: dict[str, object]) -> tuple[str, str]:
    return endpoint_disclosure(build_config_from_ui_settings(merged_ui_settings(form), Event(), dry_run=True))


def test_vision_only_run_with_remote_endpoint_discloses_that_content_may_leave() -> None:
    label, message = _disclosure({"use_llm": False, "use_vision_fallback": True, "llm_url": _REMOTE_URL})

    assert label == "EXTERNAL HTTP MODEL"
    assert "may leave this machine" in message


def test_environment_remote_endpoint_with_empty_form_is_disclosed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOLIONYM_LLM_URL", _REMOTE_URL)

    assert _disclosure({})[0] == "EXTERNAL HTTP MODEL"


@pytest.mark.parametrize("form", [{}, {"llm_url": "http://127.0.0.1:11434/v1/completions", "vision_first": True}])
def test_loopback_endpoints_stay_local(form: dict[str, object]) -> None:
    assert _disclosure(form)[0] == "LOCAL HTTP MODEL"


def test_runs_without_model_requests_keep_content_local() -> None:
    label, message = _disclosure({"use_llm": False, "llm_url": _REMOTE_URL})

    assert label == "HEURISTICS ONLY"
    assert "stays on this machine" in message


def test_unbuildable_configuration_asks_for_endpoint_review() -> None:
    assert endpoint_disclosure(None)[0] == "HTTP MODEL"
