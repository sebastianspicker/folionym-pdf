"""Filename generation pipeline orchestration."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from ..llm.cache import ResponseCache, ResponseCacheLimits, get_shared_response_cache
from ..llm.models import VisionCompletionOptions
from ..settings import RenamerConfig
from .dates import extract_date_from_content
from .loaders import default_heuristic_scorer, default_stopwords
from .metadata import resolve_filename_metadata
from .models import (
    FilenameDependencies,
    FilenameGenerationRequest,
    MetadataResolutionInput,
    ResponseCacheContext,
)
from .templates import (
    final_generated_filename,
    generate_simple_filename,
    with_structured_metadata,
)

logger = logging.getLogger(__name__)

__all__ = ["FilenameGenerationRequest", "generate_filename"]


class _DisabledLLMClient:
    """Non-networking placeholder used when the LLM features are disabled."""

    model = "disabled"
    base_url = ""

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> str:
        """Return an empty completion without contacting an LLM backend."""
        return ""

    def complete_vision(
        self,
        image_b64: str,
        prompt: str,
        options: VisionCompletionOptions | None = None,
    ) -> str:
        """Return an empty vision completion without contacting an LLM backend."""
        return ""

    def close(self) -> None:
        """No-op; this placeholder owns no resources."""
        return None


_DISABLED_LLM_CLIENT = _DisabledLLMClient()


def _get_date_str(
    pdf_content: str,
    config: RenamerConfig,
    today: date | None = None,
    pdf_metadata: dict[str, object] | None = None,
) -> str:
    """Extract date from content and optional PDF metadata fallback as YYYYMMDD."""
    content_date = extract_date_from_content(
        pdf_content,
        today=today,
        date_locale=config.output.naming.date_locale,
        prefer_leading_chars=config.output.naming.date_prefer_leading_chars or 0,
        pdf_metadata=pdf_metadata if config.extraction.use_pdf_metadata_for_date else None,
    )
    return content_date.replace("-", "")


def resolve_response_cache(config: RenamerConfig, source_path: Path | None) -> ResponseCacheContext:
    """Resolve the response cache and source-file cache key."""
    content_config = config.llm.content
    response_cache = (
        get_shared_response_cache(
            content_config.cache_dir,
            limits=ResponseCacheLimits(
                max_memory_entries=content_config.cache_max_memory_entries,
                max_memory_bytes=content_config.cache_max_memory_bytes,
                max_disk_entries=content_config.cache_max_disk_entries,
                max_disk_bytes=content_config.cache_max_disk_bytes,
                ttl_s=content_config.cache_ttl_s,
            ),
        )
        if content_config.use_cache
        else None
    )
    cache_key_base = None
    if response_cache is not None and source_path is not None and source_path.exists():
        try:
            cache_key_base = ResponseCache.build_file_key(source_path)
        except OSError as exc:
            # A file changed while its cache key was being derived. Continue
            # without persistent response caching rather than couple naming to
            # a stale identity.
            response_cache = None
            logger.warning("Skipping persistent response cache for %s: %s", source_path, exc)
    return ResponseCacheContext(response_cache, cache_key_base)


def resolve_filename_dependencies(request: FilenameGenerationRequest) -> FilenameDependencies:
    """Resolve caller-supplied generation dependencies without constructing transport."""
    config = request.config
    supplied = request.dependencies
    if config.llm.runtime.use_llm:
        cache = resolve_response_cache(config, request.context.source_path)
    else:
        cache = ResponseCacheContext()
    heuristic_scorer = supplied.heuristic_scorer or default_heuristic_scorer(config.output.naming.language)
    stopwords = supplied.stopwords or default_stopwords()
    llm_client = supplied.llm_client
    if llm_client is None:
        if config.llm.runtime.use_llm:
            raise RuntimeError("LLM-enabled filename generation requires a caller-supplied LLM client")
        else:
            # Do not construct an HTTP session for the heuristic-only path.
            # The placeholder is never invoked while
            # ``use_llm`` is false, but keeps the dependency contract explicit.
            llm_client = _DISABLED_LLM_CLIENT
    return FilenameDependencies(
        llm_client=llm_client,
        heuristic_scorer=heuristic_scorer,
        stopwords=stopwords,
        cache=cache,
    )


def generate_filename(
    pdf_content: str,
    request: FilenameGenerationRequest,
) -> tuple[str, dict[str, object]]:
    """
    Constructs the final filename and metadata:
    - date (YYYYMMDD), optionally from PDF metadata when content has no date
    - optional project
    - category (heuristic + optional LLM)
    - keywords (<=3)
    - short summary tokens (<=5)
    - optional version
    """
    if pdf_content is None or not isinstance(pdf_content, str):
        raise ValueError("pdf_content must be a non-None string")
    config = request.config
    context = request.context
    dependencies = resolve_filename_dependencies(request)
    date_str = _get_date_str(pdf_content, config, context.today, context.pdf_metadata)
    if config.llm.runtime.simple_naming_mode:
        return generate_simple_filename(pdf_content, config, date_str, dependencies)
    parts = resolve_filename_metadata(
        MetadataResolutionInput(
            pdf_content=pdf_content,
            override_category=context.override_category,
            rules=context.rules,
            cache=dependencies.cache,
        ),
        config,
        dependencies.llm_client,
        dependencies.heuristic_scorer,
        dependencies.stopwords,
    )
    structured_fields = with_structured_metadata(parts.metadata, pdf_content, config)
    filename = final_generated_filename(date_str, parts, structured_fields, config)
    return filename, parts.metadata
