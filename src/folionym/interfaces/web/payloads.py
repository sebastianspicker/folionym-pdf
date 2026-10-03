"""Full item details and lightweight immutable review summaries for the browser."""

from __future__ import annotations

from datetime import datetime

from fastapi.encoders import jsonable_encoder

from ...application.models import ApplyReport, ApplyStatus, PreviewItem, PreviewPlan, PreviewStatus


def _item_stat(item: PreviewItem, *, live: bool) -> tuple[int, str | None]:
    if not live:
        fingerprint = item.fingerprint
        if fingerprint is None:
            return 0, None
        return fingerprint.size, datetime.fromtimestamp(fingerprint.modified_ns / 1e9).astimezone().isoformat()
    try:
        current = item.source.stat(follow_symlinks=False)
        return current.st_size, datetime.fromtimestamp(current.st_mtime).astimezone().isoformat()
    except OSError:
        return 0, None


def _json_metadata(metadata: dict[str, object]) -> dict[str, object]:
    """Return JSON-compatible metadata without serializing arbitrary objects."""
    encoded = jsonable_encoder(metadata)
    return encoded if isinstance(encoded, dict) else {}


def item_payload(item: PreviewItem, *, include_metadata: bool = True) -> dict[str, object]:
    """Serialize one retained preview item for the browser."""
    size, modified = _item_stat(item, live=include_metadata)
    return {
        "id": item.id,
        "current_name": item.source.name,
        "source_path": str(item.source),
        "proposed_name": item.proposed_name,
        "status": item.status.value,
        "included": item.included,
        "reason": item.reason,
        "size": size,
        "modified_at": modified,
        "metadata": _json_metadata(item.metadata) if include_metadata else {},
    }


def plan_payload(plan: PreviewPlan, *, include_metadata: bool = True) -> dict[str, object]:
    """Serialize a preview plan and factual status counts."""
    items = [item_payload(item, include_metadata=include_metadata) for item in plan.items]
    counts = {status.value: plan.count(status) for status in PreviewStatus}
    return {
        "id": plan.id,
        "revision": plan.revision,
        "source": str(plan.source),
        "source_kind": plan.source_kind,
        "created_at": plan.created_at.isoformat(),
        "items": items,
        "counts": {"all": len(items), **counts},
    }


def report_payload(report: ApplyReport) -> dict[str, object]:
    """Serialize an exact reviewed-plan apply report."""
    items = [
        {
            "item_id": item.item_id,
            "source_name": item.source_name,
            "target_name": item.target_name,
            "status": item.status.value,
            "reason": item.reason,
        }
        for item in report.items
    ]
    counts = {status.value: report.count(status) for status in ApplyStatus}
    return {
        "id": report.id,
        "plan_id": report.plan_id,
        "source": str(report.source),
        "started_at": report.started_at.isoformat(),
        "completed_at": report.completed_at.isoformat(),
        "items": items,
        "counts": counts,
    }
