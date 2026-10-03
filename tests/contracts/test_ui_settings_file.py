"""The persisted browser/TUI settings file (~/.folionym_ui.json): defaults, schema, migration, normalization."""

from __future__ import annotations

import json
from itertools import product
from threading import Event

import pytest
from pydantic import ValidationError

from folionym.interfaces.ui_settings import (
    DEFAULT_UI_SETTINGS,
    build_config_from_ui_settings,
    load_ui_settings,
    merged_ui_settings,
    save_ui_settings,
)
from folionym.interfaces.web.schema import UISettingsPayload

_REMOTE_URL = "https://llm.remote.example/v1/completions"


def test_ui_settings_defaults_schema_and_legacy_migration_share_one_contract(tmp_path) -> None:
    assert UISettingsPayload().model_dump() == DEFAULT_UI_SETTINGS
    assert merged_ui_settings({"language": "en", "workers": "4"})["use_structured_fields"] is True

    settings_path = tmp_path / ".folionym_ui.json"
    legacy_path = tmp_path / ".folionym_tui.json"
    legacy = {"language": "en", "dry_run": False}
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    assert load_ui_settings(settings_path, legacy_path=legacy_path) == legacy
    assert json.loads(settings_path.read_text(encoding="utf-8")) == legacy


def test_existing_shared_settings_prevent_legacy_overwrite_and_schema_rejects_unknown_keys(tmp_path) -> None:
    settings_path = tmp_path / ".folionym_ui.json"
    legacy_path = tmp_path / ".folionym_tui.json"
    settings_path.write_text("{}", encoding="utf-8")
    legacy_path.write_text(json.dumps({"language": "en"}), encoding="utf-8")

    assert load_ui_settings(settings_path, legacy_path=legacy_path) == {}
    with pytest.raises(ValidationError):
        UISettingsPayload.model_validate({"unknown": "value"})


@pytest.mark.parametrize(
    ("language", "case_value", "date_format"),
    product(("de", "en"), ("camelCase", "kebabCase", "snakeCase"), ("dmy", "mdy")),
)
def test_every_browser_naming_option_round_trips_to_canonical_config(
    language: str, case_value: str, date_format: str
) -> None:
    payload = UISettingsPayload(language=language, case=case_value, date_format=date_format, use_llm=False)

    config = build_config_from_ui_settings(payload.model_dump(), Event(), dry_run=True)

    assert config.output.naming.language == language
    assert config.output.naming.desired_case == case_value
    assert config.output.naming.date_locale == date_format


def test_legacy_or_invalid_persisted_browser_choices_are_normalized() -> None:
    assert merged_ui_settings({"case": "snake_case"})["case"] == "snakeCase"
    normalized = merged_ui_settings({"language": "fr", "case": "Title Case", "date_format": "ymd"})
    assert normalized["language"] == DEFAULT_UI_SETTINGS["language"]
    assert normalized["case"] == DEFAULT_UI_SETTINGS["case"]
    assert normalized["date_format"] == DEFAULT_UI_SETTINGS["date_format"]


def test_external_endpoint_acknowledgement_is_never_persisted_or_restored(tmp_path) -> None:
    settings_path = tmp_path / ".folionym_ui.json"
    legacy_path = tmp_path / ".folionym_tui.json"
    save_ui_settings(
        {"language": "en", "acknowledged_external_endpoint": _REMOTE_URL},
        settings_path=settings_path,
    )

    stored = json.loads(settings_path.read_text(encoding="utf-8"))
    assert stored == {"language": "en", "acknowledged_external_endpoint": ""}

    settings_path.write_text(
        json.dumps({"language": "en", "acknowledged_external_endpoint": _REMOTE_URL}),
        encoding="utf-8",
    )
    loaded = load_ui_settings(settings_path, legacy_path=legacy_path)
    assert loaded == {"language": "en", "acknowledged_external_endpoint": ""}
    assert merged_ui_settings({"acknowledged_external_endpoint": _REMOTE_URL})["acknowledged_external_endpoint"] == ""


@pytest.mark.parametrize(
    ("preset", "form", "expected"),
    [
        ("scanned", {}, {"use_vision_fallback": True, "simple_naming_mode": True}),
        ("fast", {"use_llm": True}, {"use_llm": False, "min_heuristic_score": 0.6, "min_heuristic_score_gap": 0.25}),
        (
            "accurate",
            {"use_llm": False},
            {"use_llm": True, "use_single_llm_call": False, "min_heuristic_score": 0.1, "min_heuristic_score_gap": 0.0},
        ),
        ("batch", {}, {"use_cache": True, "workers": 1}),
        (
            "high-confidence-heuristic",
            {},
            {"skip_llm_category_if_heuristic_score_ge": 0.5, "skip_llm_category_if_heuristic_gap_ge": 0.3},
        ),
    ],
)
def test_selected_preset_modes_override_the_interactive_form_values(
    preset: str, form: dict[str, object], expected: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("FOLIONYM_USE_VISION_FALLBACK", "FOLIONYM_VISION_FIRST"):
        monkeypatch.delenv(name, raising=False)

    config = build_config_from_ui_settings(merged_ui_settings({**form, "preset": preset}), Event(), dry_run=True)

    resolved = {
        "use_vision_fallback": config.llm.vision.use_vision_fallback,
        "simple_naming_mode": config.llm.runtime.simple_naming_mode,
        "use_llm": config.llm.runtime.use_llm,
        "use_single_llm_call": config.llm.runtime.use_single_llm_call,
        "use_cache": config.llm.content.use_cache,
        "workers": config.output.traversal.workers,
        "min_heuristic_score": config.heuristic.scoring.min_heuristic_score,
        "min_heuristic_score_gap": config.heuristic.scoring.min_heuristic_score_gap,
        "skip_llm_category_if_heuristic_score_ge": config.heuristic.skip.skip_llm_category_if_heuristic_score_ge,
        "skip_llm_category_if_heuristic_gap_ge": config.heuristic.skip.skip_llm_category_if_heuristic_gap_ge,
    }
    assert {key: resolved[key] for key in expected} == expected
