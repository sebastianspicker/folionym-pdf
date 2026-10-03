"""End-to-end browser API workflow: preview, poll, review the plan, apply exactly, and read the report."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from folionym.interfaces.web.app import create_app

TOKEN = "workflow-session"
HEADERS = {"cookie": f"folionym_session={TOKEN}"}
INVOICE_NAME = "20260901-invoice.pdf"
LEASE_NAME = "20250315-rental-agreement.pdf"

ApiRequest = Callable[..., tuple[int, object]]


@pytest.fixture
def app(tmp_path: Path, isolated_home: Path) -> Any:
    static_dir = tmp_path / "web_dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<title>Folionym</title>", encoding="utf-8")
    return create_app(static_dir=static_dir, session_token=TOKEN)


@pytest.fixture
def api(asgi_request: Callable[..., tuple[int, dict[str, str], Any]]) -> ApiRequest:
    """Return a session-authenticated request function yielding ``(status, body)``."""

    def request(app: Any, method: str, path: str, payload: dict[str, object] | None = None) -> tuple[int, object]:
        status, _headers, body = asgi_request(app, method, path, headers=HEADERS, payload=payload)
        return status, body

    return request


def _wait_for_run(api: ApiRequest, app: Any, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        status, snapshot = api(app, "GET", f"/api/v1/runs/{run_id}")
        assert status == 200
        assert isinstance(snapshot, dict)
        if snapshot["state"] in {"completed", "failed", "cancelled"}:
            return snapshot
        time.sleep(0.05)
    pytest.fail(f"run {run_id} did not finish")


def test_preview_review_apply_and_report_rename_files_on_disk(api: ApiRequest, app: Any, pdf_dir: Path) -> None:
    status, started = api(
        app,
        "POST",
        "/api/v1/previews",
        {"source_kind": "directory", "path": str(pdf_dir), "settings": {"use_llm": False, "dry_run": False}},
    )
    assert status == 202 and isinstance(started, dict)
    preview = _wait_for_run(api, app, started["run_id"])
    assert preview["state"] == "completed" and preview["kind"] == "preview"
    assert sorted(path.name for path in pdf_dir.iterdir()) == ["a.pdf", "b.pdf"]

    status, plan = api(app, "GET", f"/api/v1/plans/{preview['plan_id']}")
    assert status == 200 and isinstance(plan, dict)
    assert plan["counts"]["all"] == 2
    proposed = {item["current_name"]: item["proposed_name"] for item in plan["items"]}
    assert proposed == {"a.pdf": INVOICE_NAME, "b.pdf": LEASE_NAME}
    ready = [item["id"] for item in plan["items"] if item["status"] == "ready"]
    assert len(ready) == 2

    status, apply_started = api(
        app,
        "POST",
        f"/api/v1/plans/{plan['id']}/apply",
        {"plan_revision": plan["revision"], "selected_ids": ready},
    )
    assert status == 202 and isinstance(apply_started, dict)
    applied = _wait_for_run(api, app, apply_started["run_id"])
    assert applied["state"] == "completed" and applied["kind"] == "apply"

    status, report = api(app, "GET", f"/api/v1/reports/{applied['report_id']}")
    assert status == 200 and isinstance(report, dict)
    assert report["counts"]["renamed"] == 2 and report["counts"]["failed"] == 0
    assert {(item["source_name"], item["target_name"], item["status"]) for item in report["items"]} == {
        ("a.pdf", INVOICE_NAME, "renamed"),
        ("b.pdf", LEASE_NAME, "renamed"),
    }
    assert sorted(path.name for path in pdf_dir.iterdir()) == [LEASE_NAME, INVOICE_NAME]
