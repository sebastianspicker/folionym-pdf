"""The documented --rules-file JSON format as seen through the CLI and the public renamer facade."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from folionym.config import build_config
from folionym.interfaces.cli import main as cli_main
from folionym.renamer import rename_pdfs_in_directory

pytestmark = pytest.mark.usefixtures("isolated_home")


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def _rules(tmp_path: Path, rules: dict[str, object]) -> Path:
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(rules), encoding="utf-8")
    return path


def test_skip_files_by_pattern_leaves_matching_files_untouched(pdf_dir: Path, tmp_path: Path) -> None:
    rules = _rules(tmp_path, {"skip_files_by_pattern": ["a.*"]})
    cli_main(["--dir", str(pdf_dir), "--no-llm", "--no-cache", "--rules-file", str(rules)])
    assert _names(pdf_dir) == ["20250315-rental-agreement.pdf", "a.pdf"]


def test_force_category_by_pattern_puts_the_category_into_the_name(pdf_dir: Path, tmp_path: Path) -> None:
    rules = _rules(tmp_path, {"force_category_by_pattern": [{"pattern": "b.pdf", "category": "zzcat"}]})
    cli_main(["--dir", str(pdf_dir), "--no-llm", "--no-cache", "--rules-file", str(rules)])
    assert _names(pdf_dir) == ["20250315-zzcat.pdf", "20260901-invoice.pdf"]


def test_rules_file_through_the_public_renamer_facade(pdf_dir: Path, tmp_path: Path) -> None:
    rules = _rules(
        tmp_path,
        {
            "skip_files_by_pattern": ["a.*"],
            "force_category_by_pattern": [{"pattern": "b.pdf", "category": "zzcat"}],
        },
    )
    config = build_config({"use_llm": False, "use_cache": False, "rules_file": str(rules)})
    rename_pdfs_in_directory(pdf_dir, config=config)
    assert _names(pdf_dir) == ["20250315-zzcat.pdf", "a.pdf"]
