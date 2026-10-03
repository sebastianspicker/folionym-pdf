"""Flat configuration keys assemble the nested backend and extraction resource limits."""

from __future__ import annotations

from folionym.settings.resolution import build_config


def test_flat_config_assembles_backend_resource_limits() -> None:
    config = build_config(
        {
            "llm_concurrency": 3,
            "cache_max_memory_entries": 7,
            "cache_max_memory_bytes": 700,
            "cache_max_disk_entries": 11,
            "cache_max_disk_bytes": 1100,
            "cache_ttl_s": 12.5,
            "vision_render_dpi": 144,
            "vision_max_pixels": 100_000,
            "vision_max_dimension_pixels": 1000,
            "vision_max_encoded_bytes": 300_000,
            "full_text_extraction": True,
        },
        env={},
    )

    assert config.llm.runtime.llm_concurrency == 3
    assert config.llm.content.cache_max_memory_entries == 7
    assert config.llm.content.cache_max_memory_bytes == 700
    assert config.llm.content.cache_max_disk_entries == 11
    assert config.llm.content.cache_max_disk_bytes == 1100
    assert config.llm.content.cache_ttl_s == 12.5
    assert config.llm.vision.vision_render_dpi == 144
    assert config.llm.vision.vision_max_pixels == 100_000
    assert config.llm.vision.vision_max_dimension_pixels == 1000
    assert config.llm.vision.vision_max_encoded_bytes == 300_000
    assert config.extraction.full_text_extraction is True
