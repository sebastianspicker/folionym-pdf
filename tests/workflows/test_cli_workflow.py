"""The installed command-line workflow: dry run, apply, rename log, undo, and plan export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from folionym.interfaces.cli import main as cli_main
from folionym.interfaces.cli.undo import main as undo_main

INVOICE_NAME = "20260901-invoice.pdf"
LEASE_NAME = "20250315-rental-agreement.pdf"

pytestmark = pytest.mark.usefixtures("isolated_home")


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def _run(directory: Path, *extra: str) -> None:
    cli_main(["--dir", str(directory), "--no-llm", "--no-cache", *extra])


def test_dry_run_leaves_files_unchanged(pdf_dir: Path) -> None:
    before = {path.name: path.read_bytes() for path in pdf_dir.iterdir()}
    _run(pdf_dir, "--dry-run")
    assert {path.name: path.read_bytes() for path in pdf_dir.iterdir()} == before


def test_apply_renames_files_and_writes_tab_separated_rename_log(pdf_dir: Path, tmp_path: Path) -> None:
    log = tmp_path / "rename.log"
    _run(pdf_dir, "--rename-log", str(log))
    assert _names(pdf_dir) == [LEASE_NAME, INVOICE_NAME]
    pairs = {tuple(line.split("\t")) for line in log.read_text(encoding="utf-8").splitlines()}
    assert pairs == {
        (str((pdf_dir / "a.pdf").resolve()), str((pdf_dir / INVOICE_NAME).resolve())),
        (str((pdf_dir / "b.pdf").resolve()), str((pdf_dir / LEASE_NAME).resolve())),
    }


def test_undo_dry_run_changes_nothing_and_undo_restores_original_names(
    pdf_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "rename.log"
    _run(pdf_dir, "--rename-log", str(log))
    renamed = _names(pdf_dir)
    assert renamed == [LEASE_NAME, INVOICE_NAME]
    capsys.readouterr()

    undo_main(["--rename-log", str(log), "--dry-run"])
    assert _names(pdf_dir) == renamed
    assert "Would revert:" in capsys.readouterr().out

    undo_main(["--rename-log", str(log)])
    assert _names(pdf_dir) == ["a.pdf", "b.pdf"]
    assert "Reverted:" in capsys.readouterr().out


def test_plan_file_is_export_only_with_old_and_new_entries(pdf_dir: Path, tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    _run(pdf_dir, "--dry-run", "--plan-file", str(plan))
    entries = json.loads(plan.read_text(encoding="utf-8"))
    assert {(Path(entry["old"]).name, Path(entry["new"]).name) for entry in entries} == {
        ("a.pdf", INVOICE_NAME),
        ("b.pdf", LEASE_NAME),
    }
    assert _names(pdf_dir) == ["a.pdf", "b.pdf"]

    # A later invocation recomputes from the PDFs; the exported plan is never consumed.
    plan.write_text(json.dumps([{"old": entries[0]["old"], "new": str(pdf_dir / "tampered.pdf")}]), encoding="utf-8")
    _run(pdf_dir)
    assert _names(pdf_dir) == [LEASE_NAME, INVOICE_NAME]
