"""
LLM backend abstraction for OpenAI-compatible HTTP servers.

Usage:
    from .http import create_llm_client_from_config, HttpLLMBackend

    client = create_llm_client_from_config(config)
    text = client.complete("your prompt here")
"""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

import requests

from ..infrastructure.http import ValidatedHttpEndpoint, validate_http_endpoint
from ..settings.environment import (
    ENV_LLM_MODEL,
    ENV_LLM_TIMEOUT,
    ENV_LLM_URL,
    ENV_REQUIRE_HTTPS,
    env_bool,
    env_float,
    env_str,
)
from .models import VisionCompletionOptions
from .protocol import LLMClient, PooledLLMClient, SerializedLLMClient

if TYPE_CHECKING:
    from ..settings import RenamerConfig

logger = logging.getLogger(__name__)

_DEFAULT_LLM_URL = "http://127.0.0.1:8080/v1/completions"
_DEFAULT_LLM_MODEL = "default"
_DEFAULT_LLM_TIMEOUT_S = 60.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validated_llm_endpoint(value: str) -> ValidatedHttpEndpoint:
    """Validate an LLM endpoint without including its value in raised errors."""
    try:
        return validate_http_endpoint(value)
    except ValueError as exc:
        raise ValueError(f"Invalid LLM endpoint URL: {exc}") from exc


def chat_completions_url(completions_url: str) -> str:
    """Derive /v1/chat/completions URL from /v1/completions URL."""
    base = (completions_url or "").strip()
    if not base:
        return "http://127.0.0.1:8080/v1/chat/completions"
    parsed = urlsplit(base)
    path = parsed.path.rstrip("/")
    # Rewrite only the terminal API suffix; the same text can legitimately
    # appear earlier in a proxy path or hostname.
    if path.endswith("/v1/completions"):
        path = path[: -len("/v1/completions")] + "/v1/chat/completions"
    elif not path.endswith("/v1/chat/completions"):
        path += "/v1/chat/completions"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


class EndpointProbeError(Exception):
    """A completions endpoint did not answer a probe with OpenAI-compatible JSON."""

    def __init__(self, url: str, cause: Exception) -> None:
        super().__init__(str(cause))
        self.url = url


def probe_completions_endpoint(url: str, model: str, *, use_chat_api: bool = False, timeout_s: float = 3.0) -> str:
    """Send a one-token request to the API family a run would use and return the probed URL.

    Proxies from the environment and redirects are not followed. Raises
    ``EndpointProbeError`` when the endpoint is unreachable or the answer is not
    OpenAI-compatible completions JSON.
    """
    payload: dict[str, object]
    if use_chat_api:
        probe_url = chat_completions_url(url)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0.0,
        }
    else:
        probe_url = url
        payload = {"model": model, "prompt": "ping", "max_tokens": 1, "temperature": 0.0}
    try:
        with requests.Session() as session:
            session.trust_env = False
            resp = session.post(probe_url, json=payload, timeout=timeout_s, allow_redirects=False)
            resp.raise_for_status()
            data = resp.json()
        if not isinstance(data, dict) or not isinstance(data.get("choices"), list):
            raise ValueError("Response is not OpenAI-compatible completions JSON.")
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        raise EndpointProbeError(probe_url, exc) from exc
    return probe_url


def _extract_chat_message_content(data: dict[str, object]) -> str:
    """Extract text content from an OpenAI-compatible chat completion response dict."""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    msg = choices[0].get("message", {})
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    return str(content).strip() if content is not None else ""


# ---------------------------------------------------------------------------
# HTTP backend
# ---------------------------------------------------------------------------


@dataclass
class HttpLLMBackend:
    """
    HTTP LLM backend. Works with any OpenAI-compatible server including:
    - llama.cpp server (default port 8080)
    - Ollama (port 11434)
    - LM Studio, vLLM, etc.

    A single requests.Session is created per backend instance for connection reuse.
    """

    base_url: str = _DEFAULT_LLM_URL
    model: str = _DEFAULT_LLM_MODEL
    timeout_s: float = _DEFAULT_LLM_TIMEOUT_S
    use_chat: bool = True
    session: requests.Session = field(default_factory=requests.Session, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Validate and normalize this instance after initialization."""
        self.base_url = _validated_llm_endpoint(self.base_url).url
        self.session.trust_env = False  # Never route LLM traffic through proxy

    def _complete_text(
        self,
        prompt: str,
        *,
        temperature: float,
        max_tokens: int | None,
        response_format: dict[str, str] | None,
    ) -> str:
        """Legacy /v1/completions text completion path."""
        payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format
        resp = self.session.post(self.base_url, json=payload, timeout=self.timeout_s, allow_redirects=False)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            logger.warning("LLM response is not a dict: %s", type(data).__name__)
            return ""
        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) == 0:
            logger.warning(
                "LLM response missing or empty 'choices' (status=%s)",
                getattr(resp, "status_code", None),
            )
            return ""
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            logger.warning(
                "LLM response 'choices[0]' is not a dict: %s",
                type(first_choice).__name__,
            )
            return ""
        text = first_choice.get("text", "")
        return str(text).strip() if text is not None else ""

    def _complete_chat(
        self,
        prompt: str,
        *,
        temperature: float,
        max_tokens: int | None,
        response_format: dict[str, str] | None,
    ) -> str:
        """Chat /v1/chat/completions path for instruct-tuned models."""
        chat_url = chat_completions_url(self.base_url)
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a document analysis assistant. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format
        resp = self.session.post(chat_url, json=payload, timeout=self.timeout_s, allow_redirects=False)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            return ""
        return _extract_chat_message_content(data)

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> str:
        """Submit a text completion request through this client."""
        try:
            if self.use_chat:
                return self._complete_chat(
                    prompt, temperature=temperature, max_tokens=max_tokens, response_format=response_format
                )
            return self._complete_text(
                prompt, temperature=temperature, max_tokens=max_tokens, response_format=response_format
            )
        except (IndexError, AttributeError, TypeError, KeyError) as exc:
            logger.warning("LLM response structure unexpected: %s", exc)
            return ""
        except requests.HTTPError as exc:
            logger.warning(
                "LLM HTTP error (status=%s; response body and endpoint redacted)",
                getattr(exc.response, "status_code", None),
            )
            return ""
        except requests.RequestException:
            logger.error("LLM unreachable. Category/summary will use heuristic or 'na' for this document.")
            return ""
        except json.JSONDecodeError:
            logger.error("LLM response is not valid JSON. Using fallback for this document.")
            return ""

    def complete_vision(
        self,
        image_b64: str,
        prompt: str,
        options: VisionCompletionOptions | None = None,
    ) -> str:
        """Send image + text prompt to the OpenAI-compatible /v1/chat/completions endpoint."""
        opts = options or VisionCompletionOptions()
        chat_url = chat_completions_url(self.base_url)
        vision_model = opts.model or self.model
        payload = {
            "model": vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{opts.image_mime_type};base64,{image_b64}"},
                        },
                    ],
                }
            ],
            "stream": False,
        }
        try:
            resp = self.session.post(chat_url, json=payload, timeout=opts.timeout_s, allow_redirects=False)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                return ""
            return _extract_chat_message_content(data)
        except requests.HTTPError as exc:
            logger.warning(
                "Vision API HTTP error (status=%s; response body and endpoint redacted)",
                getattr(exc.response, "status_code", None),
            )
            return ""
        except requests.RequestException:
            logger.warning("Vision API request failed; endpoint and response details redacted.")
            return ""
        except (
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
        ):
            logger.warning("Vision API returned an invalid response; response details redacted.")
            return ""

    def close(self) -> None:
        """Release resources owned by this client."""
        try:
            self.session.close()
        except OSError as exc:
            logger.debug("Could not close LLM session cleanly: %s", exc)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _warn_if_plaintext_remote(url: str, *, enforce: bool = False) -> None:
    """Warn or raise when PDF content will be sent to a non-loopback host over plain HTTP."""
    endpoint = _validated_llm_endpoint(url)
    if endpoint.scheme != "http" or endpoint.is_loopback:
        return
    msg = (
        "LLM endpoint uses plain HTTP with a non-loopback host. "
        "PDF content will be transmitted unencrypted. Use HTTPS for remote endpoints."
    )
    if enforce:
        raise ValueError(msg)
    logger.warning(msg)


def _resolved_timeout(config: RenamerConfig) -> float:
    """Resolve the LLM timeout from config, environment, or the default."""
    timeout_s = config.llm.backend.llm_timeout_s
    if timeout_s is not None and timeout_s > 0:
        return float(timeout_s)
    env_timeout = env_float(ENV_LLM_TIMEOUT)
    return env_timeout if env_timeout is not None and env_timeout > 0 else _DEFAULT_LLM_TIMEOUT_S


def _create_http_backend(config: RenamerConfig, *, timeout_s: float, use_chat: bool) -> HttpLLMBackend:
    """Create http backend from the resolved configuration."""
    # Configs built without build_config (e.g. RenamerConfig()) still honour the environment here.
    base_url = (config.llm.backend.llm_base_url or "").strip() or env_str(ENV_LLM_URL) or _DEFAULT_LLM_URL
    model = (config.llm.backend.llm_model or "").strip() or env_str(ENV_LLM_MODEL) or _DEFAULT_LLM_MODEL
    require_https = config.llm.runtime.require_https or env_bool(ENV_REQUIRE_HTTPS)
    _warn_if_plaintext_remote(base_url, enforce=require_https)
    return HttpLLMBackend(base_url=base_url, model=model, timeout_s=timeout_s, use_chat=use_chat)


def create_llm_client_from_config(config: RenamerConfig) -> LLMClient:
    """
    Build the HTTP LLM backend from config + env vars.

    Env vars override absent config values:
      FOLIONYM_LLM_URL       - HTTP endpoint URL
      FOLIONYM_LLM_MODEL     - model name for HTTP backend
      FOLIONYM_LLM_TIMEOUT   - timeout in seconds
    """
    timeout_s = _resolved_timeout(config)
    return _create_http_backend(config, timeout_s=timeout_s, use_chat=config.llm.runtime.llm_use_chat_api)


def create_run_scoped_llm_client(config: RenamerConfig) -> LLMClient:
    """Create a cancellation-aware client or bounded pool for one application run."""
    worker_limit = 1 if config.output.mode.interactive else max(1, config.output.traversal.workers)
    concurrency = min(max(1, config.llm.runtime.llm_concurrency), worker_limit)
    stop_event = config.output.hooks.stop_event
    clients: list[LLMClient] = []
    try:
        for _ in range(concurrency):
            clients.append(create_llm_client_from_config(config))
    except BaseException:
        for client in clients:
            with contextlib.suppress(OSError, RuntimeError):
                client.close()
        raise
    if len(clients) == 1:
        return SerializedLLMClient(clients[0], stop_event=stop_event)
    return PooledLLMClient(clients, stop_event=stop_event)
