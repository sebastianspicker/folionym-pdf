"""Loopback-only browser interface for Folionym."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .cli import main

if TYPE_CHECKING:
    from .app import create_app

__all__ = ["create_app", "main"]


def __getattr__(name: str) -> Any:
    """Import the FastAPI application factory lazily so the optional web extra is not required at import."""
    if name == "create_app":
        from .app import create_app

        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
