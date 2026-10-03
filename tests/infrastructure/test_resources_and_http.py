"""Bundled resource loading and HTTP endpoint validation primitives."""

from __future__ import annotations

import pytest

from folionym.infrastructure.http import validate_http_endpoint
from folionym.infrastructure.resources import data_path, load_json_data


def test_infrastructure_resources_and_http_validation_preserve_runtime_semantics() -> None:
    resource = data_path("meta_stopwords.json")
    assert resource.is_file()
    assert isinstance(load_json_data(resource), dict)

    endpoint = validate_http_endpoint(" https://127.0.0.1:8080/v1 ")
    assert (endpoint.url, endpoint.scheme, endpoint.hostname, endpoint.is_literal_loopback) == (
        "https://127.0.0.1:8080/v1",
        "https",
        "127.0.0.1",
        True,
    )
    with pytest.raises(ValueError, match="must not include credentials"):
        validate_http_endpoint("https://user@example.test/v1")
