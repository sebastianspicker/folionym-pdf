"""LLM document analysis for filenames: summary, keywords, category, and summary tokens.

Configuration is mapped to per-call options here, so naming orchestration
reaches the model in one hop through these functions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..llm.cache import ResponseCache
from ..llm.completion import (
    RETRY_TEMP_INCREMENT,
    JsonCompletionOptions,
    complete_json_with_retry,
    response_cache_key,
)
from ..llm.parsing import (
    CONTEXT_128K_CHUNK_OVERLAP,
    CONTEXT_128K_CHUNK_SIZE,
    CONTEXT_128K_MAX_CHARS_SINGLE,
    extract_and_validate_json,
    parse_json_field,
    truncate_for_llm,
)
from ..llm.protocol import LLMClient
from ..settings import RenamerConfig
from .models import (
    CategoryResolutionInput,
    FinalSummaryTokenInput,
    LlmMetadataResult,
    LlmSummaryInput,
)
from .prompts import (
    build_analysis_prompt,
    category_prompts,
    final_summary_prompts,
    keyword_prompts,
    summary_doc_type_hint,
    summary_prompt_chunk,
    summary_prompt_combine,
    summary_prompts_short,
)
from .scoring import PLACEHOLDER_CATEGORIES, HeuristicScorer, TopNOptions
from .tokens import split_to_tokens

logger = logging.getLogger(__name__)

DEFAULT_LLM_SUMMARY = "na"
DEFAULT_LLM_CATEGORY = "unknown"


@dataclass(frozen=True)
class DocumentAnalysisResult:
    """Normalized structured response from document analysis."""

    summary: str = DEFAULT_LLM_SUMMARY
    keywords: tuple[str, ...] = ()
    category: str = DEFAULT_LLM_CATEGORY
    final_summary_tokens: tuple[str, ...] | None = None


@dataclass(frozen=True)
class AnalysisOptions:
    """Options for single-call document analysis."""

    language: str
    temperature: float = 0.0
    lenient_json: bool = False
    max_content_chars: int | None = None
    max_content_tokens: int | None = None
    suggested_doc_type: str | None = None
    allowed_categories: list[str] | None = None
    suggested_categories: list[str] | None = None
    json_mode: bool = False
    cache: ResponseCache | None = None
    cache_key_base: str | None = None


@dataclass(frozen=True)
class SummaryOptions:
    """Options for document summarization."""

    language: str
    temperature: float = 0.0
    lenient_json: bool = False
    max_content_chars: int | None = None
    max_content_tokens: int | None = None
    max_chars_single: int = CONTEXT_128K_MAX_CHARS_SINGLE
    suggested_doc_type: str | None = None
    cache: ResponseCache | None = None
    cache_key_base: str | None = None


@dataclass(frozen=True)
class KeywordsOptions:
    """Options for keyword extraction from a summary."""

    language: str
    temperature: float = 0.0
    suggested_category: str | None = None
    lenient_json: bool = False
    cache: ResponseCache | None = None
    cache_key_base: str | None = None


@dataclass(frozen=True)
class CategoryOptions:
    """Options for LLM category classification."""

    language: str
    temperature: float = 0.0
    suggested_categories: list[str] | None = None
    allowed_categories: list[str] | None = None
    lenient_json: bool = False
    cache: ResponseCache | None = None
    cache_key_base: str | None = None


@dataclass(frozen=True)
class FinalSummaryOptions:
    """Options for deriving compact final summary tokens."""

    language: str
    temperature: float = 0.0
    lenient_json: bool = False
    cache: ResponseCache | None = None
    cache_key_base: str | None = None


@dataclass(frozen=True)
class _PromptKeyRequest:
    """Options for extracting one JSON field through fallback prompts."""

    key: str
    operation: str
    language: str
    temperature: float
    max_tokens: int | None = 1024
    lenient: bool = False
    cache: ResponseCache | None = None
    cache_key_base: str | None = None


def suggested_categories_for_llm(
    heuristic_text: str,
    config: RenamerConfig,
    heuristic_scorer: HeuristicScorer,
) -> list[str]:
    """Return the highest-scoring heuristic categories as LLM suggestions."""
    top_n = heuristic_scorer.top_n_categories(
        heuristic_text,
        TopNOptions(
            n=config.heuristic.skip.heuristic_suggestions_top_n,
            language=config.output.naming.language,
            max_score_per_category=config.heuristic.scoring.max_score_per_category,
            title_weight_region=config.heuristic.scoring.title_weight_region,
            title_weight_factor=config.heuristic.scoring.title_weight_factor,
        ),
    )
    return [c for c in top_n if c and c != "unknown"]


def _allowed_and_suggested_for_analysis(
    request: LlmSummaryInput,
    config: RenamerConfig,
    heuristic_scorer: HeuristicScorer,
) -> tuple[list[str] | None, list[str] | None]:
    """Select allowed or suggested categories for single-call analysis."""
    if request.override_category is not None:
        return (None, None)
    if request.rules is not None and request.rules.allowed_categories:
        return ([c for c in request.rules.allowed_categories if c and c.strip()], None)
    if config.heuristic.category.use_constrained_llm_category:
        return (list(heuristic_scorer.all_categories()), None)
    return (None, suggested_categories_for_llm(request.heuristic.heuristic_text, config, heuristic_scorer))


def _single_call_analysis(
    request: LlmSummaryInput,
    config: RenamerConfig,
    llm_client: LLMClient,
    heuristic_scorer: HeuristicScorer,
    effective_max_content_chars: int | None,
) -> LlmMetadataResult:
    """Run one LLM call for summary, keywords, category, and summary tokens."""
    allowed, suggested = _allowed_and_suggested_for_analysis(request, config, heuristic_scorer)
    analysis = get_document_analysis(
        llm_client,
        request.pdf_content,
        AnalysisOptions(
            language=config.output.naming.language,
            lenient_json=config.llm.runtime.lenient_llm_json,
            max_content_chars=effective_max_content_chars,
            max_content_tokens=config.llm.content.max_content_tokens,
            suggested_doc_type=request.heuristic.suggested_doc_type,
            allowed_categories=allowed,
            suggested_categories=suggested if not allowed else None,
            json_mode=config.llm.runtime.llm_json_mode,
            cache=request.cache.response_cache,
            cache_key_base=request.cache.cache_key_base,
        ),
    )
    return LlmMetadataResult(
        analysis.summary, analysis.keywords or [], analysis.category, analysis.final_summary_tokens
    )


def _multi_call_summary_keywords(
    request: LlmSummaryInput,
    config: RenamerConfig,
    llm_client: LLMClient,
    effective_max_content_chars: int | None,
) -> LlmMetadataResult:
    """Run separate LLM calls for summary and keywords."""
    summary = get_document_summary(
        llm_client,
        request.pdf_content,
        SummaryOptions(
            language=config.output.naming.language,
            lenient_json=config.llm.runtime.lenient_llm_json,
            max_content_chars=effective_max_content_chars,
            max_content_tokens=config.llm.content.max_content_tokens,
            suggested_doc_type=request.heuristic.suggested_doc_type,
            cache=request.cache.response_cache,
            cache_key_base=request.cache.cache_key_base,
        ),
    )
    cat_heur = request.heuristic.cat_heur
    raw_keywords: tuple[str, ...] | list[str] = (
        get_document_keywords(
            llm_client,
            summary,
            KeywordsOptions(
                language=config.output.naming.language,
                suggested_category=cat_heur if cat_heur != "unknown" else None,
                lenient_json=config.llm.runtime.lenient_llm_json,
                cache=request.cache.response_cache,
                cache_key_base=request.cache.cache_key_base,
            ),
        )
        or []
    )
    return LlmMetadataResult(summary, raw_keywords)


def request_document_metadata(
    request: LlmSummaryInput,
    config: RenamerConfig,
    llm_client: LLMClient,
    heuristic_scorer: HeuristicScorer,
) -> LlmMetadataResult:
    """Run LLM to get summary, keywords, and optionally a precomputed category and summary tokens."""
    effective_max_content_chars = config.llm.content.max_content_chars or config.llm.content.max_context_chars
    if config.llm.runtime.use_single_llm_call:
        return _single_call_analysis(request, config, llm_client, heuristic_scorer, effective_max_content_chars)
    return _multi_call_summary_keywords(request, config, llm_client, effective_max_content_chars)


def request_llm_category(
    request: CategoryResolutionInput,
    config: RenamerConfig,
    llm_client: LLMClient,
    heuristic_scorer: HeuristicScorer,
    allowed: list[str] | None,
) -> str:
    """Classify the document category from summary and keywords via a dedicated LLM call."""
    return get_document_category(
        llm_client,
        summary=request.summary,
        keywords=request.keywords,
        options=CategoryOptions(
            language=config.output.naming.language,
            suggested_categories=(
                suggested_categories_for_llm(request.heuristic.heuristic_text, config, heuristic_scorer)
                if not allowed
                else None
            ),
            allowed_categories=allowed,
            lenient_json=config.llm.runtime.lenient_llm_json,
            cache=request.cache.response_cache,
            cache_key_base=request.cache.cache_key_base,
        ),
    )


def resolve_final_summary_tokens(
    config: RenamerConfig,
    llm_client: LLMClient,
    request: FinalSummaryTokenInput,
) -> list[str]:
    """Resolve final summary tokens from LLM analysis or a separate LLM call."""
    if config.llm.runtime.use_single_llm_call:
        if request.precomputed_summary_tokens:
            return list(request.precomputed_summary_tokens)
        if request.summary and request.summary != "na":
            return split_to_tokens(request.summary)[:5]
        return []
    return (
        get_final_summary_tokens(
            llm_client,
            summary=request.summary,
            keywords=request.keywords,
            category=request.category,
            options=FinalSummaryOptions(
                language=config.output.naming.language,
                lenient_json=config.llm.runtime.lenient_llm_json,
                cache=request.cache.response_cache,
                cache_key_base=request.cache.cache_key_base,
            ),
        )
        or []
    )


def validate_llm_document_result(parsed: dict[str, object]) -> DocumentAnalysisResult:
    """Normalize a parsed document-analysis response and fill safe defaults."""
    return DocumentAnalysisResult(
        summary=_normalized_summary(parsed.get("summary")),
        keywords=_normalized_keywords(parsed.get("keywords")),
        category=_normalized_category(parsed.get("category")),
        final_summary_tokens=_normalized_final_summary_tokens(parsed.get("final_summary_tokens")),
    )


def _normalized_summary(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return DEFAULT_LLM_SUMMARY
    summary = value.strip()
    return DEFAULT_LLM_SUMMARY if summary.lower() == "na" else summary


def _normalized_keywords(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if item and str(item).strip())


def _normalized_category(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return DEFAULT_LLM_CATEGORY
    category = value.strip()
    return DEFAULT_LLM_CATEGORY if category.lower() in PLACEHOLDER_CATEGORIES else category


def _normalized_final_summary_tokens(value: object) -> tuple[str, ...] | None:
    if isinstance(value, list):
        cleaned = tuple(str(item).strip() for item in value if item and str(item).strip())
        return cleaned
    if isinstance(value, str) and value.strip():
        return tuple(token.strip() for token in value.split(",") if token.strip())
    return None


def _try_prompts_for_key(
    client: LLMClient,
    prompts: list[str],
    request: _PromptKeyRequest,
) -> str | list[str] | None:
    """Try prompts for key in the defined fallback order."""
    for i, prompt in enumerate(prompts):
        cache_key = response_cache_key(
            request.cache_key_base,
            operation=f"{request.operation}:{i}",
            model=client.model,
            language=request.language,
            payload=prompt,
        )
        r = complete_json_with_retry(
            client,
            prompt,
            JsonCompletionOptions(
                temperature=request.temperature + i * RETRY_TEMP_INCREMENT,
                max_tokens=request.max_tokens,
                cache=request.cache,
                cache_key=cache_key,
            ),
        )
        v = parse_json_field(r, key=request.key, lenient=request.lenient)
        if v is not None:
            return v
    return None


def get_document_analysis(
    client: LLMClient,
    pdf_content: str,
    options: AnalysisOptions,
) -> DocumentAnalysisResult:
    """Extract summary, keywords, and category from document text in a single LLM call.

    Return a DocumentAnalysisResult with empty defaults when content is too short or parsing fails.
    """
    text = _usable_document_text(pdf_content)
    if text is None:
        return DocumentAnalysisResult()

    text = _truncated_analysis_text(text, options)

    prompt = build_analysis_prompt(
        options.language,
        text,
        suggested_doc_type=options.suggested_doc_type,
        allowed_categories=options.allowed_categories,
        suggested_categories=options.suggested_categories,
    )
    raw = complete_json_with_retry(
        client,
        prompt,
        JsonCompletionOptions(
            temperature=options.temperature,
            max_retries=2,
            max_tokens=1024,
            json_mode=options.json_mode,
            cache=options.cache,
            cache_key=response_cache_key(
                options.cache_key_base,
                operation="analysis",
                model=client.model,
                language=options.language,
                payload=prompt,
            ),
        ),
    )
    return _validated_analysis_result(raw, options.lenient_json)


def _usable_document_text(pdf_content: object) -> str | None:
    """Return stripped document text only when it meets the minimum length."""
    if not isinstance(pdf_content, str):
        return None
    text = pdf_content.strip()
    return text if len(text) >= 50 else None


def _truncated_analysis_text(text: str, options: AnalysisOptions) -> str:
    """Truncate analysis input to configured character or token limits."""
    effective_max = CONTEXT_128K_MAX_CHARS_SINGLE
    if options.max_content_chars is not None:
        effective_max = min(CONTEXT_128K_MAX_CHARS_SINGLE, options.max_content_chars)
    return truncate_for_llm(text, effective_max, max_tokens=options.max_content_tokens)


def _validated_analysis_result(raw: str, lenient_json: bool) -> DocumentAnalysisResult:
    """Parse and normalize a document-analysis response."""
    try:
        data = extract_and_validate_json(
            raw,
            expected_keys={"summary", "keywords", "category"},
            lenient_keys={"summary", "keywords", "category"} if lenient_json else None,
        )
    except ValueError:
        data = {}
    return validate_llm_document_result(data)


def get_document_summary(
    client: LLMClient,
    pdf_content: str,
    options: SummaryOptions,
) -> str:
    """Generate a short document summary via LLM, chunking long content and combining partial summaries.

    Return 'na' when content is missing or too short.
    """
    text = _usable_document_text(pdf_content)
    if text is None:
        return "na"

    original_text_length = len(text)
    text = _truncated_summary_text(text, options)
    doc_type_hint = summary_doc_type_hint(options.language, options.suggested_doc_type)

    if original_text_length < options.max_chars_single:
        return _short_document_summary(client, text, doc_type_hint, options)
    return _chunked_document_summary(client, text, doc_type_hint, options)


def _truncated_summary_text(text: str, options: SummaryOptions) -> str:
    """Truncate summary input to configured character or token limits."""
    effective_max = options.max_chars_single
    if options.max_content_chars is not None:
        effective_max = min(options.max_chars_single, options.max_content_chars)
    return truncate_for_llm(text, effective_max, max_tokens=options.max_content_tokens)


def _short_document_summary(client: LLMClient, text: str, doc_type_hint: str, options: SummaryOptions) -> str:
    """Summarize a short document using fallback prompt variants."""
    prompts = summary_prompts_short(options.language, doc_type_hint, text)
    val = _try_prompts_for_key(
        client,
        prompts,
        _PromptKeyRequest(
            key="summary",
            operation="summary_short",
            language=options.language,
            temperature=options.temperature,
            lenient=options.lenient_json,
            cache=options.cache,
            cache_key_base=options.cache_key_base,
        ),
    )
    result = validate_llm_document_result({"summary": val if isinstance(val, str) else ""})
    return result.summary


def _chunked_document_summary(client: LLMClient, text: str, doc_type_hint: str, options: SummaryOptions) -> str:
    """Summarize chunks and combine their partial summaries."""
    combined = _combined_chunk_summaries(client, text, doc_type_hint, options)
    if not combined:
        return "na"
    return _combined_summary_result(client, combined, doc_type_hint, options)


def _chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    """Split document content into overlapping LLM context windows."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be < chunk_size")
    if not (text and text.strip()):
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def _combined_chunk_summaries(client: LLMClient, text: str, doc_type_hint: str, options: SummaryOptions) -> str:
    """Summarize each text chunk and concatenate successful results."""
    chunks = _chunk_text(
        text,
        chunk_size=CONTEXT_128K_CHUNK_SIZE,
        overlap=CONTEXT_128K_CHUNK_OVERLAP,
    )
    partial: list[str] = []
    for chunk in chunks:
        chunk_prompt = summary_prompt_chunk(options.language, doc_type_hint, chunk)
        r = complete_json_with_retry(
            client,
            chunk_prompt,
            JsonCompletionOptions(
                temperature=options.temperature,
                max_retries=3,
                max_tokens=1024,
                cache=options.cache,
                cache_key=response_cache_key(
                    options.cache_key_base,
                    operation=f"summary_chunk:{len(partial)}",
                    model=client.model,
                    language=options.language,
                    payload=chunk_prompt,
                ),
            ),
        )
        v = parse_json_field(r, key="summary", lenient=options.lenient_json)
        partial.append(v if isinstance(v, str) else "")
    return " ".join(p for p in partial if p)


def _combined_summary_result(client: LLMClient, combined: str, doc_type_hint: str, options: SummaryOptions) -> str:
    """Combine partial summaries into the normalized final summary."""
    final_prompt = summary_prompt_combine(options.language, doc_type_hint, combined)
    r_final = complete_json_with_retry(
        client,
        final_prompt,
        JsonCompletionOptions(
            temperature=options.temperature + RETRY_TEMP_INCREMENT,
            max_retries=3,
            max_tokens=1024,
            cache=options.cache,
            cache_key=response_cache_key(
                options.cache_key_base,
                operation="summary_combine",
                model=client.model,
                language=options.language,
                payload=final_prompt,
            ),
        ),
    )
    v_final = parse_json_field(r_final, key="summary", lenient=options.lenient_json)
    result = validate_llm_document_result({"summary": v_final if isinstance(v_final, str) else ""})
    return result.summary


def get_document_keywords(
    client: LLMClient,
    summary: str,
    options: KeywordsOptions,
) -> tuple[str, ...] | None:
    """Extract 5-7 keywords from a document summary via LLM. Return None on failure."""
    prompts = keyword_prompts(summary, options.language, options.suggested_category)
    val = _try_prompts_for_key(
        client,
        prompts,
        _PromptKeyRequest(
            key="keywords",
            operation="keywords",
            language=options.language,
            temperature=options.temperature,
            max_tokens=512,
            lenient=options.lenient_json,
            cache=options.cache,
            cache_key_base=options.cache_key_base,
        ),
    )
    result = validate_llm_document_result({"keywords": val if isinstance(val, list) else []})
    return result.keywords if result.keywords else None


def get_document_category(
    client: LLMClient,
    *,
    summary: str,
    keywords: list[str],
    options: CategoryOptions,
) -> str:
    """Classify document category via LLM, optionally constrained to allowed/suggested categories."""
    prompts = category_prompts(
        summary,
        keywords,
        language=options.language,
        allowed_categories=options.allowed_categories,
        suggested_categories=options.suggested_categories,
    )
    val = _try_prompts_for_key(
        client,
        prompts,
        _PromptKeyRequest(
            key="category",
            operation="category",
            language=options.language,
            temperature=options.temperature,
            max_tokens=256,
            lenient=options.lenient_json,
            cache=options.cache,
            cache_key_base=options.cache_key_base,
        ),
    )
    result = validate_llm_document_result({"category": _validated_raw_category(val)})
    return result.category


def _validated_raw_category(val: str | list[str] | None) -> str:
    """Reject non-string or implausibly long category responses."""
    raw = val if isinstance(val, str) else ""
    if len(raw.strip()) > 80:
        logger.info("LLM category too long (%d chars); treating as invalid.", len(raw))
        return ""
    return raw


def get_final_summary_tokens(
    client: LLMClient,
    *,
    summary: str,
    keywords: list[str],
    category: str,
    options: FinalSummaryOptions,
) -> list[str] | None:
    """Derive up to five short tokens from summary metadata via LLM."""
    prompts = final_summary_prompts(summary, keywords, category, options.language)
    val = _try_prompts_for_key(
        client,
        prompts,
        _PromptKeyRequest(
            key="final_summary",
            operation="final_summary",
            language=options.language,
            temperature=options.temperature,
            max_tokens=256,
            lenient=options.lenient_json,
            cache=options.cache,
            cache_key_base=options.cache_key_base,
        ),
    )
    return _split_final_summary_tokens(val)


def _split_final_summary_tokens(val: str | list[str] | None) -> list[str] | None:
    """Split a comma-separated summary response into at most five tokens."""
    if not isinstance(val, str):
        return None
    tokens = [t.strip() for t in val.split(",") if t.strip()]
    return tokens[:5] if tokens else None
