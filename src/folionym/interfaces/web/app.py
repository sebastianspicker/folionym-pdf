"""Loopback-only FastAPI application for the Folionym browser frontend."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from threading import Event
from urllib.parse import urlsplit

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ...application.discovery import count_directory_pdfs, list_child_directories, local_filesystem_roots
from ...application.models import PreviewPlan
from ...application.privacy import external_llm_endpoint
from ..ui_settings import build_config_from_ui_settings, load_ui_settings, merged_ui_settings
from .payloads import item_payload, plan_payload, report_payload
from .runtime import RunConflictError, RunEvent, RunRegistry
from .schema import (
    ApplyRequest,
    DirectoryEntry,
    DirectoryListing,
    PreviewRequest,
    RunStartedResponse,
    UISettingsPayload,
)
from .thumbnails import ThumbnailCache

_SESSION_COOKIE = "folionym_session"
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost"})
_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' blob:; connect-src 'self'; "
        "font-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def default_static_dir() -> Path:
    """Return the packaged Vite build directory."""
    return Path(__file__).parents[2] / "web_dist"


def _host_name(host_header: str) -> str:
    """Return a normalized hostname from the HTTP Host header."""
    if host_header.startswith("["):
        return host_header.partition("]")[0].lstrip("[")
    return host_header.rsplit(":", 1)[0].lower()


def _confined_path(path_value: str) -> Path:
    """Normalize a client-supplied path and require it to sit under a local filesystem root."""
    normalized = os.path.normpath(os.path.expanduser(path_value))
    for root in local_filesystem_roots():
        root_text = os.path.normpath(str(root))
        if normalized == root_text:
            return Path(root_text)
        if normalized.startswith(root_text.rstrip(os.sep) + os.sep):
            return Path(normalized)
    raise HTTPException(403, "Path is outside the local filesystem roots.")


def _resolve_directory(path_value: str) -> Path:
    """Resolve one absolute directory path to a readable filesystem location inside a local root."""
    expanded = os.path.expanduser(path_value)
    if not os.path.isabs(expanded):
        raise HTTPException(400, "Directory paths must be absolute.")
    candidate: str | None = None
    for root in local_filesystem_roots():
        base_real = os.path.realpath(str(root))
        resolved = os.path.realpath(os.path.join(base_real, expanded))
        if resolved == base_real or resolved.startswith(base_real.rstrip(os.sep) + os.sep):
            candidate = resolved
            break
    if candidate is None:
        raise HTTPException(403, "Path is outside the local filesystem roots.")
    if not os.path.exists(candidate):
        raise HTTPException(404, "Directory does not exist.")
    if not os.path.isdir(candidate):
        raise HTTPException(400, "Path is not a directory.")
    return Path(candidate)


def _directory_listing(path_value: str, *, include_counts: bool = True) -> DirectoryListing:
    """Build one permission-aware filesystem navigator response."""
    resolved = _resolve_directory(path_value)
    try:
        directories = list_child_directories(resolved)
    except PermissionError as exc:
        raise HTTPException(403, "Directory is not readable.") from exc
    entries = [
        DirectoryEntry(
            name=child.name, path=str(child), pdf_count=count_directory_pdfs(child) if include_counts else None
        )
        for child in directories
    ]
    parent = str(resolved.parent) if resolved.parent != resolved else None
    return DirectoryListing(
        path=str(resolved), parent=parent, entries=entries, pdf_count=count_directory_pdfs(resolved)
    )


def _is_same_local_origin(origin_header: str, host_header: str) -> bool:
    """Accept only a parsed HTTP origin exactly matching the validated request host."""
    try:
        origin = urlsplit(origin_header)
    except ValueError:
        return False
    return (
        origin.scheme == "http"
        and origin.netloc.casefold() == host_header.casefold()
        and origin.username is None
        and origin.password is None
        and origin.path == ""
        and origin.query == ""
        and origin.fragment == ""
    )


def _requires_api_session(request: Request) -> bool:
    """Return whether the request is an API call other than session bootstrap."""
    is_session_bootstrap = request.url.path == "/api/v1/session" and request.method == "GET"
    return request.url.path.startswith("/api/") and not is_session_bootstrap


def _requires_json_body(request: Request) -> bool:
    """Return whether this API method requires a JSON content type."""
    is_mutating = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    return is_mutating and not request.headers.get("content-type", "").startswith("application/json")


def _api_request_security_error(request: Request, session_token: str) -> JSONResponse | None:
    """Return the first failed API-boundary response, or ``None`` when validation passes."""
    if not _requires_api_session(request):
        return None
    if request.cookies.get(_SESSION_COOKIE) != session_token:
        return JSONResponse({"detail": "Local session required."}, status_code=403)
    origin = request.headers.get("origin")
    host = request.headers.get("host", "")
    if origin is not None and not _is_same_local_origin(origin, host):
        return JSONResponse({"detail": "Invalid request origin."}, status_code=403)
    if _requires_json_body(request):
        return JSONResponse({"detail": "JSON request required."}, status_code=415)
    return None


def _roots() -> list[DirectoryEntry]:
    """Return useful local filesystem roots without exposing file contents."""
    home = Path.home().resolve()
    return [
        DirectoryEntry(
            name="Home" if root == home else str(root),
            path=str(root),
            pdf_count=count_directory_pdfs(root),
        )
        for root in local_filesystem_roots()
    ]


def _sse_event(event: RunEvent) -> str:
    """Encode one retained run event in the Server-Sent Events wire format."""
    return f"id: {event.sequence}\nevent: {event.event}\ndata: {json.dumps(event.payload)}\n\n"


async def _event_stream(registry: RunRegistry, run_id: str, last_sequence: int) -> AsyncIterator[str]:
    """Stream retained and live run events, including keep-alive comments."""
    sequence = last_sequence
    idle_ticks = 0
    while True:
        try:
            events, terminal = registry.events_after(run_id, sequence)
        except KeyError:
            yield 'event: run.failed\ndata: {"error":"Run not found."}\n\n'
            return
        for event in events:
            sequence = event.sequence
            idle_ticks = 0
            yield _sse_event(event)
        if terminal and not events:
            return
        idle_ticks += 1
        if idle_ticks >= 40:
            idle_ticks = 0
            yield ": keep-alive\n\n"
        await asyncio.sleep(0.25)


def _external_endpoint_requirement(request: PreviewRequest, acknowledged: set[str]) -> str | None:
    """Return the normalized external model URL when acknowledgement is required.

    The decision uses the configuration the Preview will run with, so endpoints
    from ``FOLIONYM_*`` variables and vision-only runs are covered.
    """
    settings = request.settings
    try:
        config = build_config_from_ui_settings(settings.model_dump(), Event(), dry_run=True)
        endpoint = external_llm_endpoint(config)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if endpoint is None or endpoint in acknowledged:
        return None
    return endpoint


def _prepare_preview_settings(request: PreviewRequest, acknowledged: set[str]) -> dict[str, object]:
    """Validate external-boundary consent and normalize the selected source into settings."""
    endpoint = _external_endpoint_requirement(request, acknowledged)
    if endpoint is not None:
        if request.acknowledge_external_endpoint != endpoint:
            raise HTTPException(
                409,
                {
                    "code": "external_endpoint_ack_required",
                    "message": "Document-derived content may leave this machine.",
                    "endpoint": endpoint,
                },
            )
        acknowledged.add(endpoint)
    settings = request.settings.model_dump()
    settings["acknowledged_external_endpoint"] = ""
    source = str(_confined_path(request.path))
    if request.source_kind == "file":
        settings["single_file"] = source
        settings["directory"] = str(Path(source).parent)
    else:
        settings["directory"] = source
        settings["single_file"] = ""
    return settings


def _artifact_path(plan: PreviewPlan, kind: str) -> Path:
    """Resolve a configured machine-readable artifact for download."""
    paths = plan.config.output.paths
    configured: dict[str, str | Path | None] = {
        "rename-log": paths.rename_log_path,
        "metadata": paths.export_metadata_path,
        "summary": paths.summary_json_path,
    }
    value = configured.get(kind)
    if not value:
        raise HTTPException(404, "Artifact is not configured.")
    path = Path(value).expanduser()
    if not path.is_file():
        raise HTTPException(404, "Artifact is not available.")
    return path


def _install_security_middleware(app: FastAPI, session_token: str) -> None:
    """Install the loopback host, same-origin, session, and response-header boundary."""

    @app.middleware("http")
    async def local_security(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Enforce the loopback session and attach browser security headers."""
        host = request.headers.get("host", "")
        if _host_name(host) not in _ALLOWED_HOSTS:
            return JSONResponse({"detail": "Invalid local host."}, status_code=400)
        security_error = _api_request_security_error(request, session_token)
        if security_error is not None:
            return security_error
        response = await call_next(request)
        for name, value in _SECURITY_HEADERS.items():
            response.headers[name] = value
        response.headers["Cache-Control"] = (
            "no-store" if request.url.path.startswith("/api/") else response.headers.get("Cache-Control", "no-cache")
        )
        return response


def _register_source_routes(app: FastAPI, registry: RunRegistry) -> None:
    """Register bootstrap, filesystem navigation, and Preview creation."""
    request_acknowledgements: set[str] = app.state.external_endpoint_acknowledgements

    @app.get("/api/v1/session")
    def session(request: Request) -> Response:
        """Create the same-origin browser session cookie."""
        response = JSONResponse({"ready": True})
        response.set_cookie(
            _SESSION_COOKIE,
            request.app.state.session_token,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/",
        )
        return response

    @app.get("/api/v1/bootstrap")
    def bootstrap() -> dict[str, object]:
        """Return persisted settings, local roots, and available capabilities."""
        settings = UISettingsPayload.model_validate(merged_ui_settings(load_ui_settings()))
        return {
            "settings": settings.model_dump(),
            "roots": [root.model_dump() for root in _roots()],
            "capabilities": {"thumbnails": True, "ocr": True, "external_model_confirmation": True},
        }

    @app.get("/api/v1/filesystem")
    def filesystem(path: str, include_counts: bool = True) -> DirectoryListing:
        """List one absolute local directory for the folder picker."""
        return _directory_listing(path, include_counts=include_counts)

    @app.post("/api/v1/previews", response_model=RunStartedResponse, status_code=202)
    def start_preview(payload: PreviewRequest) -> RunStartedResponse:
        """Validate and enqueue one structured Preview run."""
        settings = _prepare_preview_settings(payload, request_acknowledgements)
        try:
            run_id = registry.start_preview(_confined_path(payload.path), settings)
        except RunConflictError as exc:
            raise HTTPException(409, str(exc)) from exc
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return RunStartedResponse(run_id=run_id)


def _register_run_routes(app: FastAPI, registry: RunRegistry) -> None:
    """Register run snapshots, event streaming, and cancellation."""

    @app.get("/api/v1/runs/{run_id}")
    def run_snapshot(run_id: str) -> dict[str, object]:
        """Return the latest state for one background operation."""
        try:
            return registry.snapshot(run_id)
        except KeyError as exc:
            raise HTTPException(404, "Run not found.") from exc

    @app.get("/api/v1/runs/{run_id}/events")
    def run_events(run_id: str, last_event_id: str | None = Header(default=None)) -> StreamingResponse:
        """Stream retained and live operation events."""
        try:
            sequence = int(last_event_id or "0")
        except ValueError:
            sequence = 0
        return StreamingResponse(
            _event_stream(registry, run_id, sequence),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
        )

    @app.post("/api/v1/runs/{run_id}/cancel")
    def cancel_run(run_id: str, _payload: dict[str, object]) -> dict[str, object]:
        """Request cooperative cancellation for one active operation."""
        try:
            return registry.cancel(run_id)
        except KeyError as exc:
            raise HTTPException(404, "Run not found.") from exc


def _register_plan_routes(app: FastAPI, registry: RunRegistry) -> None:
    """Register structured plan retrieval, application, and reports."""

    @app.get("/api/v1/plans/{plan_id}")
    def get_plan(plan_id: str, include_metadata: bool = True) -> dict[str, object]:
        """Return one retained structured Preview plan."""
        try:
            return plan_payload(registry.get_plan(plan_id), include_metadata=include_metadata)
        except KeyError as exc:
            raise HTTPException(404, "Preview plan not found.") from exc

    @app.post("/api/v1/plans/{plan_id}/apply", response_model=RunStartedResponse, status_code=202)
    def apply_plan(plan_id: str, payload: ApplyRequest) -> RunStartedResponse:
        """Enqueue exact application of selected reviewed targets."""
        try:
            run_id = registry.start_apply(plan_id, payload.plan_revision, payload.selected_ids)
        except KeyError as exc:
            raise HTTPException(404, "Preview plan not found.") from exc
        except RunConflictError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return RunStartedResponse(run_id=run_id)

    @app.get("/api/v1/reports/{report_id}")
    def get_report(report_id: str) -> dict[str, object]:
        """Return one retained exact-apply report."""
        try:
            return report_payload(registry.get_report(report_id))
        except KeyError as exc:
            raise HTTPException(404, "Apply report not found.") from exc


def _register_media_routes(app: FastAPI, registry: RunRegistry) -> None:
    """Register plan-owned thumbnails and configured artifacts."""
    thumbnails = ThumbnailCache()

    @app.get("/api/v1/plans/{plan_id}/items/{item_id}")
    def get_item(plan_id: str, item_id: str) -> dict[str, object]:
        """Load selected item evidence independently of the lightweight ledger."""
        try:
            plan = registry.get_plan(plan_id)
        except KeyError as exc:
            raise HTTPException(404, "Preview plan not found.") from exc
        item = next((item for item in plan.items if item.id == item_id), None)
        if item is None:
            raise HTTPException(404, "Preview item not found.")
        if item.fingerprint is not None and not item.fingerprint.matches(item.source):
            raise HTTPException(409, "The source changed after Preview. Preview again.")
        return item_payload(item)

    @app.get("/api/v1/plans/{plan_id}/items/{item_id}/thumbnail")
    def thumbnail(plan_id: str, item_id: str) -> Response:
        """Render a bounded first-page thumbnail for a plan-owned PDF."""
        try:
            plan = registry.get_plan(plan_id)
        except KeyError as exc:
            raise HTTPException(404, "Preview plan not found.") from exc
        return Response(
            thumbnails.get(plan, item_id),
            media_type="image/png",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/v1/plans/{plan_id}/artifacts/{kind}")
    def artifact(plan_id: str, kind: str) -> FileResponse:
        """Download one configured output artifact for the retained plan."""
        try:
            plan = registry.get_plan(plan_id)
        except KeyError as exc:
            raise HTTPException(404, "Preview plan not found.") from exc
        path = _artifact_path(plan, kind)
        return FileResponse(path, filename=path.name)


def _register_static_routes(app: FastAPI, static_dir: Path, session_token: str) -> None:
    """Serve packaged Vite assets and the history-fallback application shell."""
    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{route:path}", response_class=HTMLResponse)
    def spa(route: str) -> Response:
        """Serve the packaged application shell for every browser route."""
        index = static_dir / "index.html"
        if index.is_file():
            response: Response = FileResponse(index)
        else:
            response = HTMLResponse(
                "<!doctype html><title>Folionym</title><p>Frontend assets are not built.</p>",
                status_code=503,
            )
        response.set_cookie(
            _SESSION_COOKIE,
            session_token,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/",
        )
        return response


def create_app(
    *,
    registry: RunRegistry | None = None,
    static_dir: Path | None = None,
    session_token: str | None = None,
) -> FastAPI:
    """Create the loopback browser application with isolated mutable state."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    active_registry = registry or RunRegistry()
    active_token = session_token or secrets.token_urlsafe(32)
    active_static_dir = static_dir or default_static_dir()
    app.state.registry = active_registry
    app.state.session_token = active_token
    app.state.static_dir = active_static_dir
    app.state.external_endpoint_acknowledgements = set()
    _install_security_middleware(app, active_token)
    _register_source_routes(app, active_registry)
    _register_run_routes(app, active_registry)
    _register_plan_routes(app, active_registry)
    _register_media_routes(app, active_registry)
    _register_static_routes(app, active_static_dir, active_token)
    return app
