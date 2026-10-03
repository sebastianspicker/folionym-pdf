"""Configuration precedence and merging as seen through the CLI: flags, environment, then config file."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from folionym.config import RenamerConfig
from folionym.interfaces.cli import main as cli_main


def _validated_config(monkeypatch: pytest.MonkeyPatch, directory: Path, *extra: str) -> RenamerConfig:
    """Run --validate-config and return the effective configuration the CLI built."""
    cli_module = importlib.import_module("folionym.interfaces.cli.command")
    real_build_config = cli_module.build_config
    built: list[RenamerConfig] = []

    def recording_build_config(*args: Any, **kwargs: Any) -> RenamerConfig:
        config = real_build_config(*args, **kwargs)
        built.append(config)
        return config

    monkeypatch.setattr(cli_module, "build_config", recording_build_config)
    with pytest.raises(SystemExit) as exit_info:
        cli_main(["--dir", str(directory), *extra, "--validate-config"])
    assert exit_info.value.code == 0
    return built[-1]


def test_environment_beats_config_file_on_the_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("llm_model: from-file\n", encoding="utf-8")
    monkeypatch.setenv("FOLIONYM_LLM_MODEL", "from-env")

    effective = _validated_config(monkeypatch, tmp_path, "--config", str(config))

    assert effective.llm.backend.llm_model == "from-env"


def test_max_tokens_environment_beats_config_file_on_the_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("max_tokens_for_extraction: 100\n", encoding="utf-8")
    monkeypatch.setenv("FOLIONYM_MAX_TOKENS", "5")

    effective = _validated_config(monkeypatch, tmp_path, "--config", str(config))

    assert effective.extraction.max_tokens_for_extraction == 5


def test_explicit_cli_value_beats_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOLIONYM_LLM_MODEL", "from-env")

    effective = _validated_config(monkeypatch, tmp_path, "--llm-model", "from-cli")

    assert effective.llm.backend.llm_model == "from-cli"


def test_explicit_cli_value_equal_to_parser_default_beats_config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("workers: 4\n", encoding="utf-8")

    assert _validated_config(monkeypatch, tmp_path, "--config", str(config)).output.traversal.workers == 4
    explicit = _validated_config(monkeypatch, tmp_path, "--config", str(config), "--workers", "1")
    assert explicit.output.traversal.workers == 1


def test_resource_options_merge_from_cli_and_configuration_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"cache_max_memory_bytes": 4096, "cache_max_disk_entries": 10, "vision_max_pixels": 10000}),
        encoding="utf-8",
    )

    config = _validated_config(
        monkeypatch,
        tmp_path,
        "--config",
        str(config_file),
        "--no-llm",
        "--llm-concurrency",
        "2",
        "--full-text-extraction",
        "--vision-render-dpi",
        "150",
    )

    assert config.llm.runtime.llm_concurrency == 2
    assert config.llm.content.cache_max_memory_bytes == 4096
    assert config.llm.content.cache_max_disk_entries == 10
    assert config.llm.vision.vision_max_pixels == 10000
    assert config.llm.vision.vision_render_dpi == 150
    assert config.extraction.full_text_extraction is True


def test_require_https_environment_rejects_remote_http_endpoint_on_the_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FOLIONYM_REQUIRE_HTTPS", "1")

    with pytest.raises(SystemExit) as exit_info:
        cli_main(
            ["--dir", str(tmp_path), "--llm-url", "http://remote.example.test/v1/completions", "--validate-config"]
        )

    assert exit_info.value.code == 1
    assert "require_https" in capsys.readouterr().err
