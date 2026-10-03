"""Shared fixtures: real synthetic PDFs, a fake PyMuPDF module, an in-process ASGI client, and an isolated home."""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

INVOICE_TEXT = "Rechnung 01.09.2026\nRechnungsnummer INV-2026\nGesamtbetrag 100 EUR\nZahlung Rechnung"
LEASE_TEXT = "Mietvertrag 15.03.2025\nVermieter Mieter Kaution Wohnung\nMietvertrag Miete Kaution"


@pytest.fixture
def invoice_text() -> str:
    """Return German invoice text that the heuristics name ``20260901-invoice``."""
    return INVOICE_TEXT


@pytest.fixture
def lease_text() -> str:
    """Return German lease text that the heuristics name ``20250315-rental-agreement``."""
    return LEASE_TEXT


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep default logs, caches and settings files out of the real home directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def make_pdf() -> Callable[..., Path]:
    """Return a factory that writes a real one-page PDF, optionally with text and a custom page size."""

    def create(path: Path, text: str | None = None, *, width: float | None = None, height: float | None = None) -> Path:
        import fitz

        page_size = {} if width is None or height is None else {"width": width, "height": height}
        with fitz.open() as document:
            page = document.new_page(**page_size)
            if text:
                page.insert_text((50, 50), text)
            document.save(path)
        return path

    return create


@pytest.fixture
def pdf_dir(tmp_path: Path, make_pdf: Callable[..., Path]) -> Path:
    """Return a directory holding ``a.pdf`` (invoice) and ``b.pdf`` (lease)."""
    directory = tmp_path / "pdfs"
    directory.mkdir()
    make_pdf(directory / "a.pdf", INVOICE_TEXT)
    make_pdf(directory / "b.pdf", LEASE_TEXT)
    return directory


class FakePdfDocument:
    """PyMuPDF document double whose pages are text or an exception raised when the page is loaded."""

    is_encrypted = False

    def __init__(self, pages: list[str | BaseException]) -> None:
        self.pages = pages
        self.page_count = len(pages)
        self.loads: list[int] = []
        self.closed = False

    def load_page(self, page_number: int) -> SimpleNamespace:
        self.loads.append(page_number)
        value = self.pages[page_number]
        if isinstance(value, BaseException):
            raise value
        return SimpleNamespace(get_text=lambda _kind: value)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_pdf_document() -> type[FakePdfDocument]:
    """Return the fake document class so tests can build documents from page texts."""
    return FakePdfDocument


@pytest.fixture
def fake_fitz(monkeypatch: pytest.MonkeyPatch) -> Callable[[Any], Any]:
    """Return an installer that makes ``import fitz`` open the given document for any path."""

    def install(document: Any) -> Any:
        monkeypatch.setitem(sys.modules, "fitz", SimpleNamespace(open=lambda _path: document))
        return document

    return install


AsgiRequest = Callable[..., tuple[int, dict[str, str], Any]]


@pytest.fixture
def asgi_request() -> AsgiRequest:
    """Return a driver for a local ASGI app: no network listener or HTTP client dependency."""

    def request(
        app: Any,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, dict[str, str], Any]:
        path, _, query = path.partition("?")
        body = json.dumps(payload).encode() if payload is not None else b""
        request_headers = {"host": "127.0.0.1", **(headers or {})}
        if payload is not None:
            request_headers.setdefault("content-type", "application/json")
        messages: list[dict[str, Any]] = []
        received = False

        async def receive() -> dict[str, object]:
            nonlocal received
            if received:
                return {"type": "http.disconnect"}
            received = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        scope: dict[str, object] = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query.encode(),
            "headers": [(name.encode(), value.encode()) for name, value in request_headers.items()],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8765),
            "root_path": "",
        }
        asyncio.run(app(scope, receive, send))
        start = next(message for message in messages if message["type"] == "http.response.start")
        response_headers = {name.decode(): value.decode() for name, value in start["headers"]}
        raw = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
        return int(start["status"]), response_headers, json.loads(raw)

    return request
