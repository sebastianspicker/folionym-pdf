"""Configuration precedence: explicit values, then environment, then config file, then built-in defaults."""

from __future__ import annotations

import pytest

from folionym.config import build_config


def test_config_precedence_is_raw_then_environment_then_file_then_builtin() -> None:
    file_defaults = {
        "llm_base_url": "http://file.example.test/v1/completions",
        "llm_model": "file-model",
        "max_content_chars": 123,
    }
    environment = {
        "FOLIONYM_LLM_URL": "http://environment.example.test/v1/completions",
        "FOLIONYM_LLM_MODEL": "environment-model",
        "FOLIONYM_MAX_CONTENT_CHARS": "456",
    }

    from_environment = build_config({}, file_defaults=file_defaults, env=environment)
    assert from_environment.llm.backend.llm_base_url == environment["FOLIONYM_LLM_URL"]
    assert from_environment.llm.backend.llm_model == environment["FOLIONYM_LLM_MODEL"]
    assert from_environment.llm.content.max_content_chars == 456

    from_raw = build_config(
        {"llm_base_url": "http://raw.example.test/v1/completions", "llm_model": "raw-model", "max_content_chars": 789},
        file_defaults=file_defaults,
        env=environment,
    )
    assert from_raw.llm.backend.llm_base_url == "http://raw.example.test/v1/completions"
    assert from_raw.llm.backend.llm_model == "raw-model"
    assert from_raw.llm.content.max_content_chars == 789


def test_max_tokens_environment_beats_config_file_and_raw_beats_environment() -> None:
    file_defaults = {"max_tokens_for_extraction": 100}
    environment = {"FOLIONYM_MAX_TOKENS": "5"}

    assert build_config({}, file_defaults=file_defaults, env=environment).extraction.max_tokens_for_extraction == 5
    assert build_config({}, file_defaults=file_defaults, env={}).extraction.max_tokens_for_extraction == 100
    from_raw = build_config({"max_tokens_for_extraction": 7}, file_defaults=file_defaults, env=environment)
    assert from_raw.extraction.max_tokens_for_extraction == 7


def test_vision_environment_flags_are_additive_even_when_raw_values_are_false() -> None:
    config = build_config(
        {"use_vision_fallback": False, "vision_first": False},
        env={"FOLIONYM_USE_VISION_FALLBACK": "true", "FOLIONYM_VISION_FIRST": "yes"},
    )
    assert config.llm.vision.use_vision_fallback is True
    assert config.llm.vision.vision_first is True


def test_file_defaults_apply_to_every_setting_without_cli_merging(tmp_path) -> None:
    cache_dir = str(tmp_path / "file-cache")
    file_defaults = {
        "language": "en",
        "cache_dir": cache_dir,
        "post_rename_hook": "https://hook.example.test/renamed",
        "workers": 4,
    }

    config = build_config({}, file_defaults=file_defaults, env={})

    assert config.output.naming.language == "en"
    assert config.llm.content.cache_dir == cache_dir
    assert config.output.hooks.post_rename_hook == "https://hook.example.test/renamed"
    assert config.output.traversal.workers == 4


def test_environment_beats_file_and_explicit_raw_beats_environment(tmp_path) -> None:
    file_cache = str(tmp_path / "file-cache")
    env_cache = str(tmp_path / "env-cache")
    raw_cache = str(tmp_path / "raw-cache")
    environment = {"FOLIONYM_CACHE_DIR": env_cache, "FOLIONYM_POST_RENAME_HOOK": "https://env.example.test/"}
    file_defaults = {"cache_dir": file_cache, "post_rename_hook": "https://file.example.test/"}

    from_environment = build_config({}, file_defaults=file_defaults, env=environment)
    assert from_environment.llm.content.cache_dir == env_cache
    assert from_environment.output.hooks.post_rename_hook == "https://env.example.test/"

    from_raw = build_config({"cache_dir": raw_cache}, file_defaults=file_defaults, env=environment)
    assert from_raw.llm.content.cache_dir == raw_cache


def test_named_preset_values_rank_below_config_file_values(tmp_path) -> None:
    file_cache = str(tmp_path / "file-cache")

    from_preset = build_config({"preset": "batch"}, env={})
    assert from_preset.output.traversal.workers == 4

    from_file = build_config({"preset": "batch"}, file_defaults={"workers": 2, "cache_dir": file_cache}, env={})
    assert from_file.output.traversal.workers == 2
    assert from_file.llm.content.cache_dir == file_cache


def test_require_https_environment_is_additive_even_when_raw_value_is_false() -> None:
    with pytest.raises(ValueError, match="require_https"):
        build_config(
            {"require_https": False, "llm_base_url": "http://remote.example.test/v1/completions"},
            env={"FOLIONYM_REQUIRE_HTTPS": "1"},
        )
