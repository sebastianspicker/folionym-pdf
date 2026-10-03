"""Transport option containers for LLM clients."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisionCompletionOptions:
    """Optional controls for image and text completions."""

    model: str | None = None
    image_mime_type: str = "image/jpeg"
    timeout_s: float = 120.0
