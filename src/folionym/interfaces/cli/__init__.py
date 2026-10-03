"""Command-line interface entry points for Folionym.

Only the supported console launcher is exposed here, and it is loaded lazily so
importing a sibling module (for example the terminal adapter used by
``folionym.renamer``) does not load the whole CLI. Parser and runtime helpers
remain internal to this interface package.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["main"]


def __getattr__(name: str) -> Callable[..., Any]:
    if name == "main":
        from .command import main

        globals()["main"] = main
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
