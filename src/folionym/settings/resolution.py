"""Precedence, presets, and normalization for flat Folionym settings."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..infrastructure.http import validate_http_endpoint
from ..infrastructure.resources import default_cache_dir
from .environment import (
    ENV_CACHE_DIR,
    ENV_LLM_MODEL,
    ENV_LLM_TIMEOUT,
    ENV_LLM_URL,
    ENV_MAX_CONTENT_CHARS,
    ENV_MAX_CONTENT_TOKENS,
    ENV_MAX_TOKENS,
    ENV_POST_RENAME_HOOK,
    ENV_REQUIRE_HTTPS,
    ENV_USE_VISION_FALLBACK,
    ENV_VISION_FIRST,
    env_bool,
    env_str,
)
from .models import (
    _VALID_CATEGORY_DISPLAY,
    _VALID_DATE_LOCALES,
    _VALID_DESIRED_CASES,
    _VALID_LANGUAGES,
    RenamerConfig,
    build_config_from_flat_dict,
    flat_field_defaults,
)

logger = logging.getLogger(__name__)
_LLM_PRESET_DEFAULTS: dict[str, dict[str, object]] = {
    "apple-silicon": {
        "llm_model": "qwen2.5:3b",
        "llm_base_url": "http://127.0.0.1:11434/v1/completions",
        "max_context_chars": 120_000,
    },
    "gpu": {
        "llm_model": "qwen2.5:7b-instruct",
        "llm_base_url": "http://127.0.0.1:11434/v1/completions",
        "max_context_chars": 480_000,
    },
}


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def _positive_int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except TypeError, ValueError:
        return None
    return number if number > 0 else None


def _nonnegative_int_with_default(value: Any, default: int) -> int:
    """Return a non-negative integer, falling back for invalid input."""
    return max(0, _int_with_default(value, default))


def _nonnegative_float_with_default(value: Any, default: float) -> float:
    """Return a non-negative float, falling back for invalid input."""
    return max(0.0, _float_with_default(value, default))


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"1", "true", "yes", "on"}:
            return True
        if low in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def _str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    return str(value).strip() or default


def _int_with_default(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except TypeError, ValueError:
        return default


def _float_with_default(value: Any, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except TypeError, ValueError:
        return default


def _path_or_none(value: Any) -> str | Path | None:
    if value in (None, ""):
        return None
    if isinstance(value, Path):
        return value
    return _str(value) or None


def _string_or_none(value: Any) -> str | None:
    return _str(value) or None


def _first_set(*values: Any) -> Any:
    return next((value for value in values if value not in (None, "")), None)


def _text(value: Any, default: Any) -> str:
    return _str(value, default)


def _lower_text(value: Any, default: Any) -> str:
    return _str(value, default).lower()


def _flag(value: Any, default: Any) -> bool:
    return _bool(value, default)


def _integer(value: Any, default: Any) -> int:
    return _int_with_default(value, default)


def _at_least_one(value: Any, default: Any) -> int:
    return max(1, _int_with_default(value, default))


def _nonnegative_integer(value: Any, default: Any) -> int:
    return _nonnegative_int_with_default(value, default)


def _nonnegative_number(value: Any, default: Any) -> float:
    return _nonnegative_float_with_default(value, default)


def _number(value: Any, default: Any) -> float:
    return _float_with_default(value, default)


def _optional_number(value: Any, _default: Any) -> float | None:
    return _optional_float(value)


def _optional_positive_integer(value: Any, _default: Any) -> int | None:
    return _positive_int_or_none(value)


def _optional_text(value: Any, _default: Any) -> str | None:
    return _string_or_none(value)


def _optional_path(value: Any, _default: Any) -> str | Path | None:
    return _path_or_none(value)


def _as_is(value: Any, default: Any) -> Any:
    return default if value is None else value


@dataclass(frozen=True)
class _Setting:
    """Describe one flat configuration key: its coercion, default, and permitted sources.

    Values resolve as explicit raw value > environment variable > config file >
    preset > built-in default. ``additive_env`` flags skip the environment in
    that chain and are instead enabled whenever the variable is true.
    ``runtime_only`` keys accept explicit raw values only. The chain applies
    through ``build_config``; configurations constructed without it (such as
    ``RenamerConfig()``) still fall back to ``FOLIONYM_*`` variables at call
    time in ``llm.http``, ``application.hooks``, and extraction.
    """

    coerce: Callable[[Any, Any], Any]
    default: Any = None
    env: str | None = None
    additive_env: bool = False
    runtime_only: bool = False


_D = flat_field_defaults()

# Single source of truth for each flat key's environment variable and default.
# Built-in defaults are the grouped dataclass defaults in settings.models.
_SETTINGS: dict[str, _Setting] = {
    # Output naming
    "language": _Setting(_lower_text, _D["language"]),
    "desired_case": _Setting(_text, _D["desired_case"]),
    "project": _Setting(_text, _D["project"]),
    "version": _Setting(_text, _D["version"]),
    "date_locale": _Setting(_lower_text, _D["date_locale"]),
    "date_prefer_leading_chars": _Setting(_integer, _D["date_prefer_leading_chars"]),
    "max_filename_chars": _Setting(_optional_positive_integer),
    # Heuristics; override and preference inputs are folded in by _apply_heuristic_policy
    "min_heuristic_score_gap": _Setting(_number, _D["min_heuristic_score_gap"]),
    "min_heuristic_score": _Setting(_number, _D["min_heuristic_score"]),
    "title_weight_region": _Setting(_integer, _D["title_weight_region"]),
    "title_weight_factor": _Setting(_number, _D["title_weight_factor"]),
    "max_score_per_category": _Setting(_optional_number),
    "use_keyword_overlap_for_category": _Setting(_flag, _D["use_keyword_overlap_for_category"]),
    "category_display": _Setting(_lower_text, _D["category_display"]),
    "skip_llm_category_if_heuristic_score_ge": _Setting(_optional_number),
    "skip_llm_category_if_heuristic_gap_ge": _Setting(_optional_number),
    "heuristic_suggestions_top_n": _Setting(_integer, _D["heuristic_suggestions_top_n"]),
    "heuristic_score_weight": _Setting(_number, _D["heuristic_score_weight"]),
    "use_constrained_llm_category": _Setting(_flag, _D["use_constrained_llm_category"]),
    "heuristic_leading_chars": _Setting(_integer, _D["heuristic_leading_chars"]),
    "heuristic_long_doc_chars_threshold": _Setting(_integer, _D["heuristic_long_doc_chars_threshold"]),
    "heuristic_long_doc_leading_chars": _Setting(_integer, _D["heuristic_long_doc_leading_chars"]),
    "heuristic_override_min_score": _Setting(_optional_number),
    "heuristic_override_min_gap": _Setting(_optional_number),
    "no_heuristic_override": _Setting(_flag, False),
    "prefer_llm_category": _Setting(_flag, _D["prefer_llm_category"]),
    "prefer_heuristic": _Setting(_flag, False),
    # Extraction
    "max_pages_for_extraction": _Setting(_integer, _D["max_pages_for_extraction"]),
    "max_tokens_for_extraction": _Setting(_optional_positive_integer, env=ENV_MAX_TOKENS),
    "use_ocr": _Setting(_flag, _D["use_ocr"]),
    "use_structured_fields": _Setting(_flag, _D["use_structured_fields"]),
    "use_pdf_metadata_for_date": _Setting(_flag, _D["use_pdf_metadata_for_date"]),
    "full_text_extraction": _Setting(_flag, _D["full_text_extraction"]),
    # LLM backend and runtime
    "llm_base_url": _Setting(_optional_text, env=ENV_LLM_URL),
    "llm_model": _Setting(_optional_text, env=ENV_LLM_MODEL),
    "llm_timeout_s": _Setting(_optional_number, env=ENV_LLM_TIMEOUT),
    "llm_preset": _Setting(_optional_text),
    "require_https": _Setting(_flag, _D["require_https"], env=ENV_REQUIRE_HTTPS, additive_env=True),
    "use_llm": _Setting(_flag, _D["use_llm"]),
    "lenient_llm_json": _Setting(_flag, _D["lenient_llm_json"]),
    "simple_naming_mode": _Setting(_flag, _D["simple_naming_mode"]),
    "use_single_llm_call": _Setting(_flag, _D["use_single_llm_call"]),
    "llm_use_chat_api": _Setting(_flag, _D["llm_use_chat_api"]),
    "llm_json_mode": _Setting(_flag, _D["llm_json_mode"]),
    "llm_concurrency": _Setting(_at_least_one, _D["llm_concurrency"]),
    # LLM vision
    "use_vision_fallback": _Setting(_flag, _D["use_vision_fallback"], env=ENV_USE_VISION_FALLBACK, additive_env=True),
    "vision_fallback_min_text_len": _Setting(_integer, _D["vision_fallback_min_text_len"]),
    "vision_model": _Setting(_optional_text),
    "vision_first": _Setting(_flag, _D["vision_first"], env=ENV_VISION_FIRST, additive_env=True),
    "vision_render_dpi": _Setting(_at_least_one, _D["vision_render_dpi"]),
    "vision_max_pixels": _Setting(_at_least_one, _D["vision_max_pixels"]),
    "vision_max_dimension_pixels": _Setting(_at_least_one, _D["vision_max_dimension_pixels"]),
    "vision_max_encoded_bytes": _Setting(_at_least_one, _D["vision_max_encoded_bytes"]),
    # LLM content bounds and cache
    "max_context_chars": _Setting(_optional_positive_integer, env=ENV_MAX_CONTENT_CHARS),
    "max_content_chars": _Setting(_optional_positive_integer, env=ENV_MAX_CONTENT_CHARS),
    "max_content_tokens": _Setting(_optional_positive_integer, env=ENV_MAX_CONTENT_TOKENS),
    "use_cache": _Setting(_flag, _D["use_cache"]),
    "cache_dir": _Setting(_optional_path, env=ENV_CACHE_DIR),
    "cache_max_memory_entries": _Setting(_nonnegative_integer, _D["cache_max_memory_entries"]),
    "cache_max_memory_bytes": _Setting(_nonnegative_integer, _D["cache_max_memory_bytes"]),
    "cache_max_disk_entries": _Setting(_nonnegative_integer, _D["cache_max_disk_entries"]),
    "cache_max_disk_bytes": _Setting(_nonnegative_integer, _D["cache_max_disk_bytes"]),
    "cache_ttl_s": _Setting(_nonnegative_number, _D["cache_ttl_s"]),
    # Output templates, paths, and traversal
    "override_category_map": _Setting(_as_is, runtime_only=True),
    "filename_template": _Setting(_optional_text),
    "use_timestamp_fallback": _Setting(_flag, _D["use_timestamp_fallback"]),
    "timestamp_fallback_segment": _Setting(_text, _D["timestamp_fallback_segment"]),
    "backup_dir": _Setting(_optional_path),
    "rename_log_path": _Setting(_optional_path),
    "export_metadata_path": _Setting(_optional_path),
    "summary_json_path": _Setting(_optional_path),
    "plan_file_path": _Setting(_optional_path),
    "rules_file": _Setting(_optional_path),
    "workers": _Setting(_at_least_one, _D["workers"]),
    "recursive": _Setting(_flag, _D["recursive"]),
    "max_depth": _Setting(_integer, _D["max_depth"]),
    "include_patterns": _Setting(_as_is),
    "exclude_patterns": _Setting(_as_is),
    # Output mode, hooks, and progress
    "dry_run": _Setting(_flag, _D["dry_run"]),
    "skip_if_already_named": _Setting(_flag, _D["skip_if_already_named"]),
    "interactive": _Setting(_flag, _D["interactive"]),
    "manual_mode": _Setting(_flag, _D["manual_mode"], runtime_only=True),
    "write_pdf_metadata": _Setting(_flag, _D["write_pdf_metadata"]),
    "post_rename_hook": _Setting(_optional_text, env=ENV_POST_RENAME_HOOK),
    "stop_event": _Setting(_as_is, runtime_only=True),
    "progress": _Setting(_flag, _D["progress"]),
    "quiet_progress": _Setting(_flag, _D["quiet_progress"]),
    "explain": _Setting(_flag, _D["explain"]),
}


# Run-mode switches that define each named workflow preset. Interactive interfaces
# submit every form value explicitly, so they apply these over the form values.
_PRESET_MODE_VALUES: dict[str, dict[str, Any]] = {
    "scanned": {"use_vision_fallback": True, "simple_naming_mode": True},
    "fast": {"use_llm": False},
    "accurate": {"use_llm": True, "use_single_llm_call": False},
    "batch": {"use_cache": True},
}


def preset_mode_values(preset: str) -> dict[str, Any]:
    """Return the run-mode switches a named workflow preset selects, or an empty mapping."""
    return dict(_PRESET_MODE_VALUES.get(preset.strip(), {}))


def _preset_tunable_values(preset: str) -> dict[str, Any]:
    """Return the thresholds and limits a named workflow preset suggests when nothing else sets them."""
    if preset == "high-confidence-heuristic":
        return {"skip_llm_category_if_heuristic_score_ge": 0.5, "skip_llm_category_if_heuristic_gap_ge": 0.3}
    if preset == "fast":
        return {"min_heuristic_score": 0.6, "min_heuristic_score_gap": 0.25}
    if preset == "accurate":
        return {"min_heuristic_score": 0.1, "min_heuristic_score_gap": 0.0}
    if preset == "batch":
        return {"workers": 4, "cache_dir": str(default_cache_dir())}
    return {}


def _named_preset_values(preset: str) -> dict[str, Any]:
    """Return the values a named workflow preset contributes below file and environment values."""
    return {**_preset_tunable_values(preset), **preset_mode_values(preset)}


def _preset_values(raw: Mapping[str, Any], file_defaults: Mapping[str, Any]) -> dict[str, Any]:
    """Merge the named workflow preset and the LLM hardware preset into the lowest-precedence layer."""
    preset = _str(_first_set(raw.get("preset"), file_defaults.get("preset")))
    llm_preset = _string_or_none(_first_set(raw.get("llm_preset"), file_defaults.get("llm_preset")))
    effective = llm_preset if llm_preset in _LLM_PRESET_DEFAULTS else "apple-silicon"
    if llm_preset is not None and llm_preset != effective:
        logger.warning("Unknown llm_preset=%r; falling back to %r", llm_preset, effective)
    return {**_LLM_PRESET_DEFAULTS[effective], **_named_preset_values(preset)}


def _resolve_setting(
    name: str,
    setting: _Setting,
    sources: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
    env: Mapping[str, str],
) -> Any:
    """Resolve one key as explicit raw value > environment > config file > preset > built-in default."""
    raw, file_defaults, presets = sources
    if setting.runtime_only:
        return setting.coerce(raw.get(name), setting.default)
    env_value = env_str(setting.env, env) if setting.env and not setting.additive_env else None
    value = _first_set(raw.get(name), env_value, file_defaults.get(name), presets.get(name))
    resolved = setting.coerce(value, setting.default)
    if setting.additive_env and setting.env:
        return resolved or env_bool(setting.env, env)
    return resolved


def _apply_heuristic_policy(values: dict[str, Any]) -> None:
    """Fold the override-disable and heuristic-preference inputs into their configuration fields."""
    no_override = values.pop("no_heuristic_override")
    prefer_heuristic = values.pop("prefer_heuristic")
    if no_override:
        values["heuristic_override_min_score"] = values["heuristic_override_min_gap"] = None
    elif values["heuristic_override_min_score"] is None and values["heuristic_override_min_gap"] is None:
        values["heuristic_override_min_score"], values["heuristic_override_min_gap"] = 0.55, 0.3
    values["prefer_llm_category"] = values["prefer_llm_category"] and not prefer_heuristic


def _validation_errors(kwargs: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    llm_base_url = _str(kwargs.get("llm_base_url"))
    if llm_base_url:
        try:
            endpoint = validate_http_endpoint(llm_base_url)
        except ValueError as exc:
            errors.append(f"llm_base_url is invalid: {exc}")
        else:
            if _bool(kwargs.get("require_https")) and endpoint.scheme == "http" and not endpoint.is_loopback:
                errors.append("llm_base_url must use HTTPS for a non-loopback host when require_https is enabled")
    for key, choices in (
        ("language", _VALID_LANGUAGES),
        ("desired_case", _VALID_DESIRED_CASES),
        ("date_locale", _VALID_DATE_LOCALES),
        ("category_display", _VALID_CATEGORY_DISPLAY),
    ):
        default = _D[key]
        value = _str(kwargs.get(key), default).lower() if key != "desired_case" else _str(kwargs.get(key), default)
        if value not in choices:
            errors.append(f"{key}={value!r} must be one of: {', '.join(sorted(choices))}")
    return errors


def build_config(
    raw: Mapping[str, Any], *, file_defaults: Mapping[str, Any] | None = None, env: Mapping[str, str] | None = None
) -> RenamerConfig:
    """Build grouped configuration with CLI > environment > file > preset/default precedence.

    ``raw`` holds explicitly supplied values; ``None`` and empty strings count as unset.
    """
    env_map = env if env is not None else os.environ
    defaults = file_defaults or {}
    sources = (raw, defaults, _preset_values(raw, defaults))
    kwargs = {name: _resolve_setting(name, setting, sources, env_map) for name, setting in _SETTINGS.items()}
    _apply_heuristic_policy(kwargs)
    if kwargs["manual_mode"]:
        kwargs["interactive"] = True
    errors = _validation_errors(kwargs)
    if errors:
        raise ValueError("Invalid configuration:\n- " + "\n- ".join(errors))
    return build_config_from_flat_dict(kwargs)
