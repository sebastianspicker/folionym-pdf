"""Framework-free client protocols and serialization helpers."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from concurrent.futures import CancelledError
from queue import Empty, Queue
from typing import Protocol, runtime_checkable

from .models import VisionCompletionOptions


@runtime_checkable
class LLMClient(Protocol):
    """Contract implemented by text and vision completion clients."""

    @property
    def model(self) -> str: ...

    @property
    def base_url(self) -> str: ...

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> str: ...

    def complete_vision(self, image_b64: str, prompt: str, options: VisionCompletionOptions | None = None) -> str: ...

    def close(self) -> None: ...


def _raise_if_cancelled(stop_event: object | None) -> None:
    """Raise at a model-request boundary when cooperative cancellation was requested."""
    is_set = getattr(stop_event, "is_set", None)
    if callable(is_set) and is_set():
        raise CancelledError("LLM request cancelled before dispatch")


class SerializedLLMClient:
    """Serialize access to one run-scoped client shared by worker threads."""

    def __init__(self, client: LLMClient, *, stop_event: object | None = None) -> None:
        self._client = client
        self._lock = threading.Lock()
        self._stop_event = stop_event

    @property
    def model(self) -> str:
        return self._client.model

    @property
    def base_url(self) -> str:
        return self._client.base_url

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> str:
        _raise_if_cancelled(self._stop_event)
        with self._lock:
            _raise_if_cancelled(self._stop_event)
            return self._client.complete(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )

    def complete_vision(self, image_b64: str, prompt: str, options: VisionCompletionOptions | None = None) -> str:
        _raise_if_cancelled(self._stop_event)
        with self._lock:
            _raise_if_cancelled(self._stop_event)
            return self._client.complete_vision(image_b64, prompt, options)

    def close(self) -> None:
        with self._lock:
            self._client.close()


class PooledLLMClient:
    """Bound concurrent requests across independently owned LLM clients."""

    def __init__(self, clients: Sequence[LLMClient], *, stop_event: object | None = None) -> None:
        if not clients:
            raise ValueError("PooledLLMClient requires at least one client")
        self._clients = tuple(clients)
        self._available: Queue[LLMClient] = Queue(maxsize=len(self._clients))
        for client in self._clients:
            self._available.put_nowait(client)
        self._stop_event = stop_event
        self._state_changed = threading.Condition()
        self._active_count = 0
        self._closed = False

    @property
    def model(self) -> str:
        return self._clients[0].model

    @property
    def base_url(self) -> str:
        return self._clients[0].base_url

    def _acquire(self) -> LLMClient:
        """Wait for a client while observing cooperative cancellation."""
        while True:
            _raise_if_cancelled(self._stop_event)
            with self._state_changed:
                if self._closed:
                    raise RuntimeError("LLM client pool is closed")
            try:
                client = self._available.get(timeout=0.05)
            except Empty:
                continue
            with self._state_changed:
                if self._closed:
                    self._available.put_nowait(client)
                    raise RuntimeError("LLM client pool is closed")
                self._active_count += 1
            return client

    def _release(self, client: LLMClient) -> None:
        """Return one independently owned client to the pool."""
        self._available.put_nowait(client)
        with self._state_changed:
            self._active_count -= 1
            self._state_changed.notify_all()

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> str:
        client = self._acquire()
        try:
            _raise_if_cancelled(self._stop_event)
            return client.complete(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        finally:
            self._release(client)

    def complete_vision(self, image_b64: str, prompt: str, options: VisionCompletionOptions | None = None) -> str:
        client = self._acquire()
        try:
            _raise_if_cancelled(self._stop_event)
            return client.complete_vision(image_b64, prompt, options)
        finally:
            self._release(client)

    def close(self) -> None:
        """Close every independently owned client once."""
        with self._state_changed:
            if self._closed:
                return
            self._closed = True
            while self._active_count:
                self._state_changed.wait()
        first_error: BaseException | None = None
        for client in self._clients:
            try:
                client.close()
            except (OSError, RuntimeError) as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error
