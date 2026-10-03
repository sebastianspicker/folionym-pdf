"""Browser run registry: bounded history, SSE resume, plan retention, and expiry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from folionym.application.models import FileFingerprint, PreviewItem, PreviewPlan, PreviewStatus
from folionym.interfaces.web.runtime import RunRegistry
from folionym.settings import RenamerConfig


def _plan(tmp_path: Path) -> PreviewPlan:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"synthetic")
    item = PreviewItem(
        id="item",
        source=source,
        proposed_base="invoice",
        metadata={"summary": "x" * 10000},
        status=PreviewStatus.READY,
        included=True,
        fingerprint=FileFingerprint.capture(source),
    )
    return PreviewPlan("plan", tmp_path, "directory", RenamerConfig(), (item,), datetime.now(UTC))


def test_history_is_bounded_and_old_sse_cursor_resumes_with_current_snapshot(tmp_path: Path) -> None:
    registry = RunRegistry(max_terminal_runs=2, event_history=3)
    for _ in range(10):
        run = registry._new_run("preview")
        registry._finish(run, message="done")
    assert len(registry._runs) == 2
    active = registry._new_run("preview")
    for current in range(20):
        registry._progress(active, current, 20, tmp_path / "source.pdf")
    assert len(active.events) == 3
    events, terminal = registry.events_after(active.id, 0)
    assert len(events) == 1 and events[0].event == "run.snapshot"
    assert events[0].payload["completed"] == 19 and not terminal
    assert registry.events_after(active.id, events[0].sequence) == ([], False)
    registry._finish(active, message="done")
    following, terminal = registry.events_after(active.id, events[0].sequence)
    assert terminal and [event.event for event in following] == ["run.completed"]


def test_eviction_keeps_active_apply_plan_then_releases_unreferenced_artifacts(tmp_path: Path) -> None:
    registry = RunRegistry(max_terminal_runs=1)
    plan = _plan(tmp_path)
    preview = registry._new_run("preview")
    registry._plans[plan.id] = plan
    preview.plan_id = plan.id
    registry._finish(preview, message="done")
    apply = registry._new_run("apply", plan_id=plan.id)
    preview.completed_at = datetime.now(UTC) - timedelta(hours=2)
    registry.snapshot(apply.id)
    assert preview.id not in registry._runs and registry.get_plan(plan.id) is plan
    registry._finish(apply, message="done")
    next_run = registry._new_run("preview")
    registry._finish(next_run, message="done")
    assert plan.id not in registry._plans


def test_expired_plan_cannot_be_read_or_rescued_by_apply(tmp_path: Path) -> None:
    registry = RunRegistry(retention_seconds=1)
    plan = _plan(tmp_path)
    preview = registry._new_run("preview")
    registry._plans[plan.id] = plan
    preview.plan_id = plan.id
    registry._finish(preview, message="done")
    preview.completed_at = datetime.now(UTC) - timedelta(seconds=2)
    with pytest.raises(KeyError):
        registry.start_apply(plan.id, plan.revision, ["item"])
    with pytest.raises(KeyError):
        registry.get_plan(plan.id)
    assert not registry._runs
