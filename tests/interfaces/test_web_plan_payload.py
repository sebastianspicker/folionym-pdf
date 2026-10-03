"""Browser plan payloads: the lightweight summary stats from Preview and omits metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from folionym.application.models import FileFingerprint, PreviewItem, PreviewPlan, PreviewStatus
from folionym.interfaces.web.payloads import plan_payload
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


def test_lightweight_summary_uses_preview_stat_and_omits_metadata(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    original_size = plan.items[0].source.stat().st_size
    plan.items[0].source.unlink()
    summary = plan_payload(plan, include_metadata=False)
    full = plan_payload(plan)
    assert summary["items"][0]["size"] == original_size
    assert summary["items"][0]["metadata"] == {}
    assert full["items"][0]["size"] == 0
    assert full["items"][0]["metadata"] == plan.items[0].metadata
    assert summary["counts"] == full["counts"]
