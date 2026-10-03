"""Names and parsing of the FOLIONYM_* environment variables that feed configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping

ENV_LLM_URL = "FOLIONYM_LLM_URL"
ENV_LLM_MODEL = "FOLIONYM_LLM_MODEL"
ENV_LLM_TIMEOUT = "FOLIONYM_LLM_TIMEOUT"
ENV_REQUIRE_HTTPS = "FOLIONYM_REQUIRE_HTTPS"
ENV_MAX_TOKENS = "FOLIONYM_MAX_TOKENS"
ENV_MAX_CONTENT_CHARS = "FOLIONYM_MAX_CONTENT_CHARS"
ENV_MAX_CONTENT_TOKENS = "FOLIONYM_MAX_CONTENT_TOKENS"
ENV_CACHE_DIR = "FOLIONYM_CACHE_DIR"
ENV_OCR_LANG = "FOLIONYM_OCR_LANG"
ENV_POST_RENAME_HOOK = "FOLIONYM_POST_RENAME_HOOK"
ENV_USE_VISION_FALLBACK = "FOLIONYM_USE_VISION_FALLBACK"
ENV_VISION_FIRST = "FOLIONYM_VISION_FIRST"

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def env_str(name: str, env: Mapping[str, str] | None = None) -> str | None:
    """Return the stripped value of *name*, or None when it is unset or blank."""
    source = os.environ if env is None else env
    return (source.get(name) or "").strip() or None


def env_bool(name: str, env: Mapping[str, str] | None = None) -> bool:
    """Return whether *name* holds a recognized true value (1, true, yes, on)."""
    return (env_str(name, env) or "").lower() in _TRUE_VALUES


def env_float(name: str, env: Mapping[str, str] | None = None) -> float | None:
    """Return *name* as a float, or None when it is unset, blank, or not a number."""
    value = env_str(name, env)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
