"""Recoverable exception groups for operator-facing boundaries."""

from __future__ import annotations

import json

import requests


class DataFileError(ValueError):
    """A bundled or user-supplied JSON data file could not be parsed."""


COMMON_RECOVERABLE_EXCEPTIONS = (
    json.JSONDecodeError,
    KeyError,
    OSError,
    requests.RequestException,
    RuntimeError,
    TypeError,
    ValueError,
)
