"""Pooled, run-scoped, and serialized LLM clients: concurrency, cleanup, and cancellation."""

from __future__ import annotations

import threading
import time
from concurrent.futures import CancelledError, ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from folionym.llm import http as llm_http
from folionym.llm.protocol import PooledLLMClient, SerializedLLMClient
from folionym.settings.models import LLMConfig, LLMRuntimeConfig, OutputConfig, OutputTraversalConfig, RenamerConfig


class _ConcurrentClient:
    model = "model"
    base_url = "http://test.invalid"

    def __init__(self, state: SimpleNamespace, identifier: int) -> None:
        self.state = state
        self.identifier = identifier
        self.closed = False

    def complete(self, *_args: object, **_kwargs: object) -> str:
        with self.state.lock:
            self.state.active += 1
            self.state.peak = max(self.state.peak, self.state.active)
        time.sleep(0.04)
        with self.state.lock:
            self.state.active -= 1
        return str(self.identifier)

    def complete_vision(self, *_args: object, **_kwargs: object) -> str:
        return self.complete()

    def close(self) -> None:
        self.closed = True


def test_llm_pool_uses_independently_owned_clients_concurrently() -> None:
    state = SimpleNamespace(lock=threading.Lock(), active=0, peak=0)
    clients = [_ConcurrentClient(state, number) for number in range(4)]
    pool = PooledLLMClient(clients)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _number: pool.complete("prompt"), range(4)))
    pool.close()

    assert state.peak == 4
    assert set(results) == {"0", "1", "2", "3"}
    assert all(client.closed for client in clients)


def test_run_scoped_factory_clamps_pool_to_workers_and_cleans_partial_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SimpleNamespace(lock=threading.Lock(), active=0, peak=0)
    created: list[_ConcurrentClient] = []

    def create(_config: RenamerConfig) -> _ConcurrentClient:
        client = _ConcurrentClient(state, len(created))
        created.append(client)
        if len(created) == 3:
            raise RuntimeError("factory failed")
        return client

    monkeypatch.setattr(llm_http, "create_llm_client_from_config", create)
    config = RenamerConfig(
        llm=LLMConfig(runtime=LLMRuntimeConfig(llm_concurrency=4)),
        output=OutputConfig(traversal=OutputTraversalConfig(workers=3)),
    )

    with pytest.raises(RuntimeError, match="factory failed"):
        llm_http.create_run_scoped_llm_client(config)
    assert all(client.closed for client in created[:2])


def test_serialized_client_propagates_cancellation_before_model_dispatch() -> None:
    stop_event = threading.Event()
    state = SimpleNamespace(lock=threading.Lock(), active=0, peak=0)
    raw = _ConcurrentClient(state, 0)
    client = SerializedLLMClient(raw, stop_event=stop_event)
    stop_event.set()

    with pytest.raises(CancelledError):
        client.complete("prompt")
    assert state.peak == 0
