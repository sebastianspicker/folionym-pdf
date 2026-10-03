"""The documented --config file formats (JSON, YAML, YML) change filename options."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from folionym.interfaces.cli import main as cli_main

pytestmark = pytest.mark.usefixtures("isolated_home")


@pytest.mark.parametrize(
    ("config_name", "config_text"),
    [
        ("config.json", json.dumps({"case": "snakeCase", "project": "Acme"})),
        ("config.yaml", "case: snakeCase\nproject: Acme\n"),
        ("config.yml", "case: snakeCase\nproject: Acme\n"),
    ],
)
def test_config_file_changes_filename_options(
    pdf_dir: Path, tmp_path: Path, config_name: str, config_text: str
) -> None:
    config = tmp_path / config_name
    config.write_text(config_text, encoding="utf-8")
    cli_main(["--dir", str(pdf_dir), "--no-llm", "--no-cache", "--config", str(config)])
    assert sorted(path.name for path in pdf_dir.iterdir()) == [
        "20250315-acme-rental-agreement.pdf",
        "20260901-acme-invoice.pdf",
    ]
