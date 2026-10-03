"""Generic JSON completion with retries and response caching."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .cache import ResponseCache
from .parsing import extract_and_validate_json
from .protocol import LLMClient

logger = logging.getLogger(__name__)

# Temperature increment per retry attempt when LLM JSON parsing fails.
RETRY_TEMP_INCREMENT = 0.2


@dataclass(frozen=True)
class JsonCompletionOptions:
    """Control JSON completion retries, output mode, and caching."""

    temperature: float = 0.0
    max_retries: int = 3
    max_tokens: int | None = 1024
    json_mode: bool = False
    cache: ResponseCache | None = None
    cache_key: str | None = None


@dataclass(frozen=True)
class JsonCompletionResult:
    """Hold a completion response and whether it parsed as JSON."""

    response: str
    valid: bool


def response_cache_key(
    cache_key_base: str | None,
    *,
    operation: str,
    model: str,
    language: str,
    payload: str,
) -> str | None:
    """Build a stable response-cache key for one LLM operation, or None without a base key."""
    if not cache_key_base:
        return None
    return ResponseCache.derive_response_key(
        cache_key_base,
        operation=operation,
        model=model,
        language=language,
        extra=payload,
    )


def complete_json_with_retry(
    client: LLMClient,
    prompt: str,
    options: JsonCompletionOptions | None = None,
) -> str:
    """Retry LLM completion up to max_retries times, increasing temperature, until valid JSON."""
    opts = options or JsonCompletionOptions()
    if cached := _cached_llm_response(opts):
        return cached
    result = _complete_json_attempts(client, prompt, opts)
    if result.valid:
        _store_cached_llm_response(opts, result.response)
        return result.response
    logger.error(
        "LLM returned no valid JSON after %s retries. Using heuristic or 'na' for this document.",
        _effective_retries(opts),
    )
    return result.response


def _cached_llm_response(options: JsonCompletionOptions) -> str | None:
    """Return a cached completion when both cache and key are available."""
    if options.cache is None or options.cache_key is None:
        return None
    cached = options.cache.get(options.cache_key)
    if cached is not None:
        logger.debug("LLM cache hit for %s", options.cache_key)
    return cached


def _store_cached_llm_response(options: JsonCompletionOptions, response: str) -> None:
    """Store a completion when caching is configured."""
    if options.cache is not None and options.cache_key is not None:
        options.cache.set(options.cache_key, response)


def _effective_retries(options: JsonCompletionOptions) -> int:
    """Use one attempt in server-enforced JSON mode; otherwise use the retry limit."""
    return 1 if options.json_mode else options.max_retries


def _response_format(options: JsonCompletionOptions) -> dict[str, str] | None:
    """Return the OpenAI-compatible JSON response-format request when enabled."""
    return {"type": "json_object"} if options.json_mode else None


def _complete_json_attempts(client: LLMClient, prompt: str, options: JsonCompletionOptions) -> JsonCompletionResult:
    """Attempt completion until valid JSON is received or retries are exhausted."""
    temp = options.temperature
    last = ""
    for attempt in range(_effective_retries(options)):
        last = client.complete(
            prompt,
            temperature=temp,
            max_tokens=options.max_tokens,
            response_format=_response_format(options),
        )
        if _is_valid_json_response(last):
            return JsonCompletionResult(last, valid=True)
        temp += RETRY_TEMP_INCREMENT
        logger.info("Retry %s: New temperature=%s", attempt + 1, temp)
    return JsonCompletionResult(last, valid=False)


def _is_valid_json_response(response: str) -> bool:
    """Return whether a response contains a parseable JSON object."""
    try:
        extract_and_validate_json(response)
    except ValueError:
        return False
    return True
