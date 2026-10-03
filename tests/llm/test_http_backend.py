"""HTTP LLM backend: chat payload, loopback transport policy, and error redaction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from folionym.llm.http import HttpLLMBackend


def test_llm_transport_uses_chat_payload_without_proxy_or_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = HttpLLMBackend(base_url="http://127.0.0.1:8080/v1/completions", model="local-model")
    response = MagicMock()
    response.json.return_value = {"choices": [{"message": {"content": "  answer  "}}]}
    response.raise_for_status.return_value = None
    calls: list[tuple[str, dict[str, object]]] = []

    def post(url: str, **kwargs: object) -> MagicMock:
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(backend.session, "post", post)
    assert (
        backend.complete("document-derived prompt", max_tokens=42, response_format={"type": "json_object"}) == "answer"
    )
    assert backend.session.trust_env is False
    assert calls[0][0] == "http://127.0.0.1:8080/v1/chat/completions"
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["json"] == {
        "model": "local-model",
        "messages": [
            {"role": "system", "content": "You are a document analysis assistant. Respond only with valid JSON."},
            {"role": "user", "content": "document-derived prompt"},
        ],
        "temperature": 0.0,
        "max_tokens": 42,
        "response_format": {"type": "json_object"},
    }


def test_llm_http_errors_redact_endpoint_body_and_prompt(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "provider-secret"
    backend = HttpLLMBackend(use_chat=False)
    response = MagicMock(status_code=502)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise requests.HTTPError(f"endpoint?token={secret} body={secret}", response=response)

    monkeypatch.setattr(backend.session, "post", fail)
    caplog.set_level("WARNING", logger="folionym.llm.http")
    assert backend.complete(f"prompt containing {secret}") == ""
    assert secret not in caplog.text
    assert "response body and endpoint redacted" in caplog.text


def test_endpoint_probe_uses_the_run_api_family_and_reports_the_probed_url() -> None:
    import json as _json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from folionym.llm.http import EndpointProbeError, probe_completions_endpoint

    seen: list[tuple[str, dict[str, object]]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = _json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((self.path, body))
            payload = b'{"choices": []}' if self.path.endswith("/chat/completions") else b"not json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args: object) -> None:
            return None

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}/v1/completions"
    try:
        probed = probe_completions_endpoint(base, "m", use_chat_api=True)
        with pytest.raises(EndpointProbeError) as failure:
            probe_completions_endpoint(base, "m")
    finally:
        server.shutdown()

    assert probed.endswith("/v1/chat/completions")
    assert failure.value.url == base
    assert seen[0][1]["messages"] == [{"role": "user", "content": "ping"}]
    assert seen[1][1]["prompt"] == "ping"
