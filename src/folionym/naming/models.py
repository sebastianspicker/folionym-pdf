"""Small request/result containers for filename generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ..llm.cache import ResponseCache
from ..llm.protocol import LLMClient
from ..settings import RenamerConfig
from .rules import ProcessingRules
from .scoring import HeuristicScorer
from .tokens import Stopwords


@dataclass(frozen=True)
class ResponseCacheContext:
    """Cache and base key shared by LLM calls for one source file."""

    response_cache: ResponseCache | None = None
    cache_key_base: str | None = None


@dataclass(frozen=True)
class HeuristicCategorySignal:
    """Heuristic category candidate and confidence signals."""

    heuristic_text: str
    cat_heur: str
    heuristic_score: float
    heuristic_gap: float
    suggested_doc_type: str | None = None


@dataclass(frozen=True)
class CategoryResolutionInput:
    """Inputs required to reconcile heuristic and LLM categories."""

    heuristic: HeuristicCategorySignal
    summary: str
    keywords: list[str]
    rules: ProcessingRules | None = None
    precomputed_llm_category: str | None = None
    cache: ResponseCacheContext = field(default_factory=ResponseCacheContext)


@dataclass(frozen=True)
class LlmSummaryInput:
    """Inputs required to obtain LLM-derived filename metadata."""

    pdf_content: str
    heuristic: HeuristicCategorySignal
    override_category: str | None
    rules: ProcessingRules | None = None
    cache: ResponseCacheContext = field(default_factory=ResponseCacheContext)


@dataclass(frozen=True)
class LlmMetadataResult:
    """LLM-derived metadata returned by one analysis path."""

    summary: str
    raw_keywords: list[str] | tuple[str, ...]
    precomputed_category: str | None = None
    precomputed_summary_tokens: list[str] | tuple[str, ...] | None = None


@dataclass(frozen=True)
class FinalSummaryTokenInput:
    """Inputs used to derive final summary tokens."""

    summary: str
    keywords: list[str]
    category: str
    precomputed_summary_tokens: list[str] | tuple[str, ...] | None = None
    cache: ResponseCacheContext = field(default_factory=ResponseCacheContext)


@dataclass(frozen=True)
class MetadataResolutionInput:
    """Document and optional overrides used to resolve filename metadata."""

    pdf_content: str
    override_category: str | None
    rules: ProcessingRules | None = None
    cache: ResponseCacheContext = field(default_factory=ResponseCacheContext)


@dataclass(frozen=True)
class FilenameGenerationDependencies:
    """Optional caller-supplied filename-generation dependencies."""

    llm_client: LLMClient | None = None
    heuristic_scorer: HeuristicScorer | None = None
    stopwords: Stopwords | None = None


@dataclass(frozen=True)
class FilenameGenerationContext:
    """Per-document context for filename generation."""

    override_category: str | None = None
    today: date | None = None
    pdf_metadata: dict[str, object] | None = None
    rules: ProcessingRules | None = None
    source_path: Path | None = None


@dataclass(frozen=True)
class FilenameGenerationRequest:
    """Configuration, dependencies, and context for one filename request."""

    config: RenamerConfig
    dependencies: FilenameGenerationDependencies = FilenameGenerationDependencies()
    context: FilenameGenerationContext = FilenameGenerationContext()

    @property
    def llm_client(self) -> LLMClient | None:
        """Return the optional caller-supplied LLM client."""
        return self.dependencies.llm_client

    # Read accessors below are part of the public folionym.filename facade.
    @property
    def heuristic_scorer(self) -> HeuristicScorer | None:
        """Return the optional caller-supplied heuristic scorer."""
        return self.dependencies.heuristic_scorer

    @property
    def stopwords(self) -> Stopwords | None:
        """Return the optional caller-supplied stopword set."""
        return self.dependencies.stopwords

    @property
    def override_category(self) -> str | None:
        """Return the optional category override."""
        return self.context.override_category

    @property
    def today(self) -> date | None:
        """Return the optional date used for deterministic extraction."""
        return self.context.today

    @property
    def pdf_metadata(self) -> dict[str, object] | None:
        """Return the optional PDF metadata fallback."""
        return self.context.pdf_metadata

    @property
    def rules(self) -> ProcessingRules | None:
        """Return the optional processing rules for this request."""
        return self.context.rules

    @property
    def source_path(self) -> Path | None:
        """Return the source path used for cache identity."""
        return self.context.source_path


@dataclass(frozen=True)
class FilenameDependencies:
    """Resolved dependencies used during filename generation."""

    llm_client: LLMClient
    heuristic_scorer: HeuristicScorer
    stopwords: Stopwords
    cache: ResponseCacheContext = field(default_factory=ResponseCacheContext)


@dataclass(frozen=True)
class FilenameMetadataParts:
    """Cleaned metadata parts used to assemble the final filename."""

    category_for_filename: str
    category_clean: list[str]
    keyword_clean: list[str]
    summary_clean: list[str]
    metadata: dict[str, object]
