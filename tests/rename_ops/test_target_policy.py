"""Exact-target versus unique-available target policy of the rename entry point."""

from __future__ import annotations

from pathlib import Path

from folionym.rename_ops import RenameApplyOptions, apply_single_rename


def test_exact_target_policy_refuses_an_occupied_name_while_unique_available_picks_a_suffix(tmp_path: Path) -> None:
    exact_source = tmp_path / "exact.pdf"
    unique_source = tmp_path / "unique.pdf"
    exact_source.write_bytes(b"exact")
    unique_source.write_bytes(b"unique")
    (tmp_path / "target.pdf").write_bytes(b"occupied")

    exact_ok, _ = apply_single_rename(exact_source, "target", RenameApplyOptions(exact_target=True))
    unique_ok, unique_target = apply_single_rename(unique_source, "target", RenameApplyOptions())

    assert not exact_ok
    assert exact_source.read_bytes() == b"exact"
    assert unique_ok
    assert unique_target != tmp_path / "target.pdf"
    assert unique_target.read_bytes() == b"unique"
    assert (tmp_path / "target.pdf").read_bytes() == b"occupied"
