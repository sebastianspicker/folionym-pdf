"""Persisted run exports: plan file, metadata (JSON and CSV), summary, and rename log."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import folionym.application.batch as batch
import folionym.renamer as renamer
from folionym.application.models import Proposal
from folionym.config import build_config

METADATA = {
    "category": "invoice",
    "summary": "August invoice",
    "keywords": ["august", "invoice"],
    "category_source": "heuristic",
    "llm_failed": False,
    "used_vision_fallback": False,
    "invoice_id": "INV-1",
    "amount": "10.00",
    "company": "Example",
}


def test_plan_mode_and_real_rename_preserve_their_distinct_artifact_contracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"pdf")
    plan_path = tmp_path / "plan.json"
    metadata_path = tmp_path / "metadata.json"
    summary_path = tmp_path / "summary.json"
    log_path = tmp_path / "rename.log"
    plan_config = build_config(
        {
            "use_llm": False,
            "dry_run": False,
            "plan_file_path": str(plan_path),
        }
    )
    monkeypatch.setattr(
        batch,
        "produce_proposals",
        lambda files, _config, **_kwargs: [Proposal(files[0], "approved-invoice", METADATA)],
    )

    planned = renamer.rename_pdfs_in_directory(tmp_path, config=plan_config)

    target = tmp_path / "approved-invoice.pdf"
    assert planned == {target}
    assert source.exists() and not target.exists()
    assert json.loads(plan_path.read_text(encoding="utf-8")) == [{"old": str(source), "new": str(target)}]

    apply_config = build_config(
        {
            "use_llm": False,
            "dry_run": False,
            "export_metadata_path": str(metadata_path),
            "summary_json_path": str(summary_path),
            "rename_log_path": str(log_path),
        }
    )
    renamed = renamer.rename_pdfs_in_directory(tmp_path, config=apply_config)

    assert renamed == {target}
    exported = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert exported == [{"path": str(source), "new_name": target.name, **METADATA}]
    assert json.loads(summary_path.read_text(encoding="utf-8")) == {
        "directory": str(tmp_path),
        "processed": 1,
        "renamed": 1,
        "skipped": 0,
        "failed": 0,
        "dry_run": False,
        "failures": [],
    }
    assert log_path.read_text(encoding="utf-8") == f"{source}\t{target}\n"


def test_metadata_export_json_and_csv_schemas_remain_machine_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    risky = {**METADATA, "summary": "=SUM(1)"}
    monkeypatch.setattr(
        batch,
        "produce_proposals",
        lambda files, _config, **_kwargs: [Proposal(files[0], "approved-invoice", risky)],
    )
    exports: dict[str, Path] = {}
    for suffix in ("json", "csv"):
        directory = tmp_path / suffix
        directory.mkdir()
        (directory / "source.pdf").write_bytes(b"pdf")
        exports[suffix] = directory / f"metadata.{suffix}"
        config = build_config({"use_llm": False, "dry_run": False, "export_metadata_path": str(exports[suffix])})
        renamer.rename_pdfs_in_directory(directory, config=config)

    rows = [{"path": str(tmp_path / "json" / "source.pdf"), "new_name": "approved-invoice.pdf", **risky}]
    assert exports["json"].read_text(encoding="utf-8") == json.dumps(rows, ensure_ascii=False, indent=2)

    with exports["csv"].open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        (row,) = list(reader)
        assert reader.fieldnames == [
            "path",
            "new_name",
            "category",
            "summary",
            "keywords",
            "category_source",
            "llm_failed",
            "used_vision_fallback",
            "invoice_id",
            "amount",
            "company",
        ]
    assert row["path"] == str(tmp_path / "csv" / "source.pdf")
    assert row["new_name"] == "approved-invoice.pdf"
    assert row["summary"] == "'=SUM(1)"
