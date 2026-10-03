"""Optional tiktoken access with one thread-safe, per-encoding cache.

``tiktoken`` is imported lazily and never required: when it is missing or an
encoding cannot be loaded, callers receive ``None`` and token counting falls
back to a four-characters-per-token heuristic.
"""

from __future__ import annotations

import threading
from typing import Any

DEFAULT_ENCODING_NAME = "cl100k_base"

# Any: tiktoken lacks type stubs.
_MISSING = object()  # sentinel: load failed, do not retry
_encodings: dict[str, Any] = {}
_lock = threading.Lock()


def _load_encoding(name: str) -> Any:
    """Load one named encoding, returning the sentinel when it is unavailable."""
    try:
        import tiktoken

        return tiktoken.get_encoding(name)
    except ImportError, KeyError, RuntimeError, ValueError, LookupError:
        return _MISSING


def get_encoding(name: str = DEFAULT_ENCODING_NAME) -> Any | None:
    """Return the cached tiktoken encoding for `name`, or None when unavailable."""
    encoding = _encodings.get(name)
    if encoding is None:
        with _lock:
            encoding = _encodings.get(name)
            if encoding is None:  # double-checked locking
                encoding = _load_encoding(name)
                _encodings[name] = encoding
    return None if encoding is _MISSING else encoding


def encoding_for_model(model_hint: str | None) -> Any | None:
    """Return the cached encoding for a model name (default encoding without a hint), or None."""
    if not model_hint:
        return get_encoding()
    try:
        import tiktoken

        name = tiktoken.encoding_name_for_model(model_hint)
    except ImportError, KeyError, RuntimeError, ValueError, LookupError:
        return None
    return get_encoding(name)


def count_tokens(text: str) -> int:
    """Count tokens with cached tiktoken support, falling back to a four-character heuristic."""
    encoding = get_encoding()
    if encoding is not None:
        # fmt: off
        try:
            return len(encoding.encode(text))
        except (AttributeError, RuntimeError, ValueError):
            pass
        # fmt: on
    # Fallback heuristic: ~4 chars per token for typical text.
    return max(1, len(text) // 4)


def reset_encoding_cache() -> None:
    """Forget cached encodings, including remembered load failures."""
    with _lock:
        _encodings.clear()
