"""Contracts for the shared optional tiktoken counter."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from types import SimpleNamespace

import pytest

from folionym.infrastructure import tokens


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    tokens.reset_encoding_cache()
    yield
    tokens.reset_encoding_cache()


def test_encoding_is_loaded_once_per_name(monkeypatch: pytest.MonkeyPatch) -> None:
    loads: list[str] = []

    def get_encoding(name: str) -> SimpleNamespace:
        loads.append(name)
        return SimpleNamespace(name=name, encode=lambda text: text.split())

    fake = SimpleNamespace(get_encoding=get_encoding, encoding_name_for_model=lambda _model: "o200k_base")
    monkeypatch.setitem(sys.modules, "tiktoken", fake)

    assert tokens.count_tokens("a b c") == 3
    assert tokens.count_tokens("a b") == 2
    assert tokens.get_encoding() is tokens.get_encoding()
    assert tokens.encoding_for_model("gpt-x") is tokens.encoding_for_model("gpt-y")
    assert loads == ["cl100k_base", "o200k_base"]


def test_missing_tiktoken_falls_back_to_character_heuristic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "tiktoken", None)

    assert tokens.get_encoding() is None
    assert tokens.encoding_for_model("gpt-4") is None
    assert tokens.encoding_for_model(None) is None
    assert tokens.count_tokens("x" * 40) == 10
    assert tokens.count_tokens("") == 1


def test_unknown_model_has_no_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    def unknown(_model: str) -> str:
        raise KeyError("unknown")

    fake = SimpleNamespace(get_encoding=lambda _name: object(), encoding_name_for_model=unknown)
    monkeypatch.setitem(sys.modules, "tiktoken", fake)

    assert tokens.encoding_for_model("not-a-model") is None
