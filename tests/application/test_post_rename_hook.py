"""Post-rename hook URL policy: no credentials, no plain HTTP, no proxies, no redirects."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from folionym.application import hooks as renamer_hooks
from folionym.infrastructure.http import post_json_without_redirects


def test_post_rename_hook_rejects_unsafe_urls_proxies_and_redirects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    response = MagicMock(status_code=204)
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeSession:
        trust_env = True

        def __enter__(self) -> FakeSession:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, url: str, **kwargs: object) -> MagicMock:
            calls.append((url, kwargs))
            return response

    session = FakeSession()
    monkeypatch.setattr(requests, "Session", lambda: session)
    old_path, new_path = tmp_path / "old.pdf", tmp_path / "new.pdf"
    renamer_hooks.run_post_rename_hook("https://hooks.example.test/rename", old_path, new_path, {})
    assert not session.trust_env
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["timeout"] == 10

    for unsafe in ("https://user:secret@example.test/hook", "http://example.test/hook"):
        renamer_hooks.run_post_rename_hook(unsafe, old_path, new_path, {})
    assert len(calls) == 1

    response.status_code = 302
    with pytest.raises(requests.TooManyRedirects):
        post_json_without_redirects("https://hooks.example.test/redirect", {}, timeout=10)
