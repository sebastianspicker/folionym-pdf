"""ASGI contracts for the loopback browser interface."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from folionym.application.models import FileFingerprint, PreviewItem, PreviewPlan, PreviewStatus
from folionym.config import RenamerConfig
from folionym.interfaces.web.app import create_app
from folionym.interfaces.web.runtime import RunRegistry

AsgiRequest = Callable[..., tuple[int, dict[str, str], Any]]


def _app_with_plan(tmp_path: Path) -> tuple[Any, RunRegistry, PreviewPlan]:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"pdf")
    static_dir = tmp_path / "web_dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<title>Folionym</title>", encoding="utf-8")
    item = PreviewItem(
        id="item-1",
        source=source,
        proposed_base="reviewed-invoice",
        metadata={"category": "invoice"},
        status=PreviewStatus.READY,
        included=True,
        fingerprint=FileFingerprint.capture(source),
    )
    plan = PreviewPlan(
        id="plan-1",
        source=tmp_path,
        source_kind="directory",
        config=RenamerConfig(),
        items=(item,),
        created_at=datetime(2026, 8, 27, tzinfo=UTC),
        revision=3,
    )
    registry = RunRegistry()
    registry._plans[plan.id] = plan
    return create_app(registry=registry, static_dir=static_dir, session_token="test-session"), registry, plan


def test_plan_serialization_and_stale_revision_rejection_are_stable(tmp_path: Path, asgi_request: AsgiRequest) -> None:
    app, _registry, plan = _app_with_plan(tmp_path)

    missing_status, _missing_headers, missing_body = asgi_request(app, "GET", f"/api/v1/plans/{plan.id}")
    assert (missing_status, missing_body) == (403, {"detail": "Local session required."})

    session_status, session_headers, session_body = asgi_request(app, "GET", "/api/v1/session")
    assert (session_status, session_body) == (200, {"ready": True})
    assert session_headers["content-security-policy"].startswith("default-src 'self'")
    assert session_headers["x-frame-options"] == "DENY"
    assert session_headers["cache-control"] == "no-store"
    cookie = session_headers["set-cookie"].partition(";")[0]

    status, _headers, response = asgi_request(app, "GET", f"/api/v1/plans/{plan.id}", headers={"cookie": cookie})
    assert status == 200
    assert response == {
        "id": "plan-1",
        "revision": 3,
        "source": str(tmp_path),
        "source_kind": "directory",
        "created_at": "2026-08-27T00:00:00+00:00",
        "items": [
            {
                "id": "item-1",
                "current_name": "source.pdf",
                "source_path": str(tmp_path / "source.pdf"),
                "proposed_name": "reviewed-invoice.pdf",
                "status": "ready",
                "included": True,
                "reason": None,
                "size": 3,
                "modified_at": response["items"][0]["modified_at"],
                "metadata": {"category": "invoice"},
            }
        ],
        "counts": {"all": 1, "ready": 1, "review": 0, "skipped": 0, "failed": 0},
    }

    stale_status, _stale_headers, stale_body = asgi_request(
        app,
        "POST",
        f"/api/v1/plans/{plan.id}/apply",
        headers={"cookie": cookie},
        payload={"plan_revision": 2, "selected_ids": ["item-1"]},
    )
    assert (stale_status, stale_body) == (422, {"detail": "The preview plan revision is stale."})


def test_cancel_route_preserves_cooperative_cancellation_state(tmp_path: Path, asgi_request: AsgiRequest) -> None:
    app, registry, _plan = _app_with_plan(tmp_path)
    _session_status, session_headers, _session_body = asgi_request(app, "GET", "/api/v1/session")
    run = registry._new_run("preview")

    status, _headers, response = asgi_request(
        app,
        "POST",
        f"/api/v1/runs/{run.id}/cancel",
        headers={"cookie": session_headers["set-cookie"].partition(";")[0]},
        payload={},
    )

    assert status == 200
    assert response["state"] == "queued"
    assert response["message"] == "Cancelling after the active file"
    assert run.stop_event.is_set()
    events, terminal = registry.events_after(run.id, 0)
    assert [event.event for event in events] == ["run.queued", "run.cancelling"]
    assert terminal is False


def test_lightweight_plan_and_selected_detail_routes_keep_review_contract(
    tmp_path: Path, asgi_request: AsgiRequest
) -> None:
    app, _registry, plan = _app_with_plan(tmp_path)
    headers = {"cookie": "folionym_session=test-session"}
    status, _, summary = asgi_request(
        app,
        "GET",
        f"/api/v1/plans/{plan.id}?include_metadata=false",
        headers=headers,
    )
    assert status == 200 and summary["items"][0]["metadata"] == {}
    detail_status, _, detail = asgi_request(
        app,
        "GET",
        f"/api/v1/plans/{plan.id}/items/item-1",
        headers=headers,
    )
    assert detail_status == 200 and detail["metadata"] == {"category": "invoice"}
    assert detail["id"] == summary["items"][0]["id"]
    forbidden, _, _ = asgi_request(app, "GET", f"/api/v1/plans/{plan.id}/items/item-1")
    assert forbidden == 403


def test_shallow_directory_route_reports_unknown_child_counts(tmp_path: Path, asgi_request: AsgiRequest) -> None:
    app, _, _ = _app_with_plan(tmp_path)
    (tmp_path / "child").mkdir()
    status, _, listing = asgi_request(
        app,
        "GET",
        f"/api/v1/filesystem?path={tmp_path}&include_counts=false",
        headers={"cookie": "folionym_session=test-session"},
    )
    assert status == 200 and listing["pdf_count"] == 1
    assert all(entry["pdf_count"] is None for entry in listing["entries"])


def test_selected_detail_refuses_evidence_from_a_changed_source(tmp_path: Path, asgi_request: AsgiRequest) -> None:
    app, _, plan = _app_with_plan(tmp_path)
    plan.items[0].source.write_bytes(b"changed")
    status, _, _ = asgi_request(
        app,
        "GET",
        f"/api/v1/plans/{plan.id}/items/item-1",
        headers={"cookie": "folionym_session=test-session"},
    )
    assert status == 409


def test_bootstrap_returns_settings_roots_and_capabilities(
    tmp_path: Path, isolated_home: Path, asgi_request: AsgiRequest
) -> None:
    static_dir = tmp_path / "web_dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<title>Folionym</title>", encoding="utf-8")
    app = create_app(static_dir=static_dir, session_token="bootstrap-session")

    status, _headers, body = asgi_request(
        app, "GET", "/api/v1/bootstrap", headers={"cookie": "folionym_session=bootstrap-session"}
    )

    assert status == 200
    assert isinstance(body, dict)
    assert set(body) == {"settings", "roots", "capabilities"}


_REMOTE_URL = "https://llm.remote.example/v1/completions"


@pytest.mark.parametrize(
    ("environment", "form"),
    [
        ({"FOLIONYM_LLM_URL": _REMOTE_URL}, {}),
        ({}, {"use_llm": False, "use_vision_fallback": True, "llm_url": _REMOTE_URL}),
        ({"FOLIONYM_LLM_URL": _REMOTE_URL, "FOLIONYM_VISION_FIRST": "1"}, {"use_llm": False}),
    ],
)
def test_preview_requires_acknowledgement_for_the_endpoint_the_run_will_contact(
    tmp_path: Path,
    asgi_request: AsgiRequest,
    monkeypatch: pytest.MonkeyPatch,
    environment: dict[str, str],
    form: dict[str, object],
) -> None:
    for name in ("FOLIONYM_LLM_URL", "FOLIONYM_USE_VISION_FALLBACK", "FOLIONYM_VISION_FIRST"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    app, registry, _ = _app_with_plan(tmp_path)
    started: list[dict[str, object]] = []
    monkeypatch.setattr(registry, "start_preview", lambda _source, settings: started.append(settings) or "run-1")
    request = {"source_kind": "directory", "path": str(tmp_path), "settings": form}
    headers = {"cookie": "folionym_session=test-session"}

    status, _, body = asgi_request(app, "POST", "/api/v1/previews", headers=headers, payload=request)
    assert status == 409
    assert body["detail"]["code"] == "external_endpoint_ack_required"
    assert body["detail"]["endpoint"] == _REMOTE_URL
    assert started == []

    acknowledged = {**request, "acknowledge_external_endpoint": True}
    status, _, _ = asgi_request(app, "POST", "/api/v1/previews", headers=headers, payload=acknowledged)
    assert status == 202
    assert started[-1]["acknowledged_external_endpoint"] == _REMOTE_URL


def test_preview_with_a_loopback_endpoint_needs_no_acknowledgement(
    tmp_path: Path, asgi_request: AsgiRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOLIONYM_LLM_URL", "http://127.0.0.1:11434/v1/completions")
    app, registry, _ = _app_with_plan(tmp_path)
    monkeypatch.setattr(registry, "start_preview", lambda _source, _settings: "run-1")
    request = {"source_kind": "directory", "path": str(tmp_path), "settings": {"use_vision_fallback": True}}

    status, _, _ = asgi_request(
        app, "POST", "/api/v1/previews", headers={"cookie": "folionym_session=test-session"}, payload=request
    )

    assert status == 202
