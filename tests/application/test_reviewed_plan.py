"""Reviewed plans apply exact previewed targets and refuse stale, colliding, or cancelled work."""

from __future__ import annotations

import threading
from pathlib import Path

from folionym.application import reviewed_plan
from folionym.application.models import Proposal
from folionym.application.reviewed_plan import ApplyStatus, apply_reviewed_plan, create_preview_plan
from folionym.config import build_config


def _preview_plan_with_proposals(tmp_path: Path, monkeypatch, proposals: list[str]):
    sources = []
    for index, _proposal in enumerate(proposals, start=1):
        source = tmp_path / f"source-{index}.pdf"
        source.write_bytes(b"pdf")
        sources.append(source)
    config = build_config({"use_llm": False, "dry_run": True})
    monkeypatch.setattr(
        reviewed_plan,
        "produce_proposals",
        lambda files, _config, **_kwargs: [
            Proposal(path, proposal, {"category": "invoice"}) for path, proposal in zip(files, proposals, strict=True)
        ],
    )
    return create_preview_plan(tmp_path, config)


def test_reviewed_plan_rejects_a_source_that_changed_after_preview(tmp_path: Path, monkeypatch) -> None:
    plan = _preview_plan_with_proposals(tmp_path, monkeypatch, ["approved"])
    plan.items[0].source.write_bytes(b"changed pdf bytes")

    report = apply_reviewed_plan(plan, [plan.items[0].id])

    assert report.items[0].status is ApplyStatus.FAILED
    assert report.items[0].reason == "The source changed after Preview."
    assert plan.items[0].source.exists()
    assert not (tmp_path / "approved.pdf").exists()


def test_reviewed_plan_binds_source_identity_at_the_mutation_boundary(tmp_path: Path, monkeypatch) -> None:
    plan = _preview_plan_with_proposals(tmp_path, monkeypatch, ["approved"])
    source = plan.items[0].source
    original_reject = reviewed_plan.reject_source_symlink

    def replace_after_preflight(path: Path) -> None:
        original_reject(path)
        path.unlink()
        path.write_bytes(b"replacement after review")

    monkeypatch.setattr(reviewed_plan, "reject_source_symlink", replace_after_preflight)

    report = apply_reviewed_plan(plan, [plan.items[0].id])

    assert report.items[0].status is ApplyStatus.FAILED
    assert "Source changed after Preview" in (report.items[0].reason or "")
    assert source.read_bytes() == b"replacement after review"
    assert not (tmp_path / "approved.pdf").exists()


def test_reviewed_plan_rejects_each_selected_exact_target_collision(tmp_path: Path, monkeypatch) -> None:
    plan = _preview_plan_with_proposals(tmp_path, monkeypatch, ["approved", "approved"])

    report = apply_reviewed_plan(plan, [item.id for item in plan.items])

    assert [item.status for item in report.items] == [ApplyStatus.FAILED, ApplyStatus.FAILED]
    assert [item.reason for item in report.items] == [
        "Another selected item has the same reviewed target.",
        "Another selected item has the same reviewed target.",
    ]
    assert all(item.source.exists() for item in plan.items)
    assert not (tmp_path / "approved.pdf").exists()


def test_reviewed_plan_refuses_an_occupied_exact_target_without_selecting_a_suffix(tmp_path: Path, monkeypatch) -> None:
    plan = _preview_plan_with_proposals(tmp_path, monkeypatch, ["approved"])
    occupied = tmp_path / "approved.pdf"
    occupied.write_bytes(b"occupied")

    report = apply_reviewed_plan(plan, [plan.items[0].id])

    assert report.items[0].status is ApplyStatus.FAILED
    assert report.items[0].reason == "The reviewed target already exists."
    assert occupied.read_bytes() == b"occupied"
    assert plan.items[0].source.exists()
    assert not (tmp_path / "approved_1.pdf").exists()


def test_reviewed_apply_honours_a_stop_event_set_before_the_worker_starts(tmp_path: Path, monkeypatch) -> None:
    plan = _preview_plan_with_proposals(tmp_path, monkeypatch, ["approved"])
    stop_event = threading.Event()
    stop_event.set()

    report = apply_reviewed_plan(plan, [plan.items[0].id], stop_event=stop_event)

    assert [item.status for item in report.items] == [ApplyStatus.CANCELLED]
    assert plan.items[0].source.exists()
    assert not (tmp_path / "approved.pdf").exists()
