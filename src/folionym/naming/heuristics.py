"""Heuristic/LLM category reconciliation and LLM category normalization."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..infrastructure.resources import category_aliases_path
from .scoring import PLACEHOLDER_CATEGORIES

logger = logging.getLogger(__name__)


__all__ = [
    "CategoryCombineOptions",
    "CategoryCombineParams",
    "combine_categories",
    "normalize_llm_category",
]


def _load_category_aliases() -> dict[str, str]:
    """Load alias map: LLM output (lowercase, _) -> heuristic category."""
    path = _category_aliases_path_or_none()
    if path is None:
        return {}
    return _category_aliases_cached(path, _path_mtime_ns(path))


# Include mtime in the cache key so local alias-file edits are visible to watch mode.
@lru_cache(maxsize=4)
def _category_aliases_cached(path: Path, _mtime_ns: int) -> dict[str, str]:
    """Read category aliases through the mtime-sensitive cache."""
    return _read_category_aliases(path)


def _category_aliases_path_or_none() -> Path | None:
    """Return the category-alias file path when available."""
    try:
        return category_aliases_path()
    except (
        ValueError,
        FileNotFoundError,
    ):
        return None


def _path_mtime_ns(path: Path) -> int:
    """Return a file modification timestamp, or zero when unavailable."""
    try:
        return path.stat().st_mtime_ns if path.exists() else 0
    except OSError:
        return 0


def _read_category_aliases(path: Path) -> dict[str, str]:
    """Load and normalize category aliases, returning an empty map on failure."""
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        aliases = data.get("aliases") if isinstance(data, dict) else {}
        return _normalized_alias_map(aliases if isinstance(aliases, dict) else {})
    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
    ):
        return {}


def _normalized_alias_map(aliases: dict[Any, Any]) -> dict[str, str]:
    """Normalize alias keys to the category-comparison form."""
    return {str(k).strip().lower().replace(" ", "_"): str(v) for k, v in aliases.items() if k and v}


def normalize_llm_category(cat_llm: str | None, *, _aliases: dict[str, str] | None = None) -> str:
    """Map LLM category to heuristic vocabulary to reduce false conflicts."""
    if not cat_llm or not isinstance(cat_llm, str):
        return ""
    # Preserve hierarchy markers as token separators instead of deleting them.
    cleaned = cat_llm.replace("/", "_")
    key = re.sub(r"[^\w\s-]", "", cleaned).strip().lower().replace(" ", "_")
    if not key or key in PLACEHOLDER_CATEGORIES:
        return key if key else "unknown"
    aliases = _aliases if _aliases is not None else _load_category_aliases()
    return aliases.get(key, key)


def _tokenize_for_overlap(text: str) -> set[str]:
    """Lowercase token set from category or context."""
    if not text or not isinstance(text, str):
        return set()
    tokens = re.split(r"[\s_]+", text.lower())
    return {t for t in tokens if t and t.isalnum()}


def _overlap_count(category_tokens: set[str], context_tokens: set[str]) -> int:
    """Number of category tokens that appear in context."""
    return len(category_tokens & context_tokens)


@dataclass(frozen=True)
class CategoryCombineParams:
    """Parameters that control how heuristic and LLM categories are merged."""

    prefer_llm: bool = True
    min_heuristic_score: float = 0.0
    heuristic_override_min_score: float | None = None
    heuristic_override_min_gap: float | None = None
    heuristic_score_weight: float = 1.0
    use_keyword_overlap: bool = False


@dataclass(frozen=True)
class CategoryCombineOptions:
    """Per-document heuristic signals plus the configured combination parameters."""

    heuristic_score: float | None = None
    heuristic_gap: float | None = None
    params: CategoryCombineParams = field(default_factory=CategoryCombineParams)
    context_for_overlap: str | None = None
    category_parent_map: dict[str, str] | None = None


def _combine_apply_heuristic_override(
    cat_heuristic: str,
    cat_llm_norm: str,
    opts: CategoryCombineOptions,
) -> str | None:
    """If high-confidence heuristic override applies, return cat_heuristic; else None."""
    params = opts.params
    if params.heuristic_override_min_score is None or params.heuristic_override_min_gap is None:
        return None
    if opts.heuristic_score is None or opts.heuristic_gap is None:
        return None
    if (
        opts.heuristic_score < params.heuristic_override_min_score
        or opts.heuristic_gap < params.heuristic_override_min_gap
    ):
        return None
    logger.info(
        "High-confidence heuristic (score=%.2f gap=%.2f). Using %s.",
        opts.heuristic_score,
        opts.heuristic_gap,
        cat_heuristic,
    )
    logger.info(
        "CategoryConflict chosen=heuristic llm=%s heuristic=%s",
        cat_llm_norm,
        cat_heuristic,
    )
    return cat_heuristic


def _combine_agreement_or_parent(
    cat_llm_norm: str,
    cat_heuristic: str,
    category_parent_map: dict[str, str] | None,
) -> str | None:
    """If exact, parent, or sibling agreement, return category; else None."""
    if cat_llm_norm == cat_heuristic:
        return cat_heuristic
    if not category_parent_map:
        return None
    heur_parent = category_parent_map.get(cat_heuristic)
    llm_parent = category_parent_map.get(cat_llm_norm)
    if heur_parent == cat_llm_norm:
        logger.info(
            "LLM %s and heuristic %s agree (parent match). Using more specific: heuristic.",
            cat_llm_norm,
            cat_heuristic,
        )
        return cat_heuristic
    if llm_parent == cat_heuristic:
        logger.info(
            "LLM %s and heuristic %s agree (parent match). Using more specific: LLM.",
            cat_llm_norm,
            cat_heuristic,
        )
        return cat_llm_norm
    if heur_parent is not None and llm_parent is not None and heur_parent == llm_parent:
        logger.info(
            "Sibling categories (parent=%s). Using heuristic %s.",
            heur_parent,
            cat_heuristic,
        )
        logger.info(
            "CategoryConflict chosen=heuristic llm=%s heuristic=%s",
            cat_llm_norm,
            cat_heuristic,
        )
        return cat_heuristic
    return None


def _combine_resolve_conflict(
    cat_llm_norm: str,
    cat_heuristic: str,
    opts: CategoryCombineOptions,
) -> str:
    """Resolve conflict via keyword overlap or preference."""
    context_pick = _context_conflict_pick(cat_llm_norm, cat_heuristic, opts)
    if context_pick is not None:
        return context_pick
    return _preference_conflict_pick(cat_llm_norm, cat_heuristic, opts.params.prefer_llm)


def _context_conflict_pick(
    cat_llm_norm: str,
    cat_heuristic: str,
    opts: CategoryCombineOptions,
) -> str | None:
    """Resolve a conflict from overlap context when enabled."""
    if not opts.context_for_overlap:
        return None
    if opts.params.use_keyword_overlap:
        return _overlap_conflict_pick(cat_llm_norm, cat_heuristic, opts)
    return None


def _overlap_conflict_pick(
    cat_llm_norm: str,
    cat_heuristic: str,
    opts: CategoryCombineOptions,
) -> str:
    """Choose the category favored by weighted keyword overlap."""
    overlap_llm, overlap_heur_weighted = _weighted_overlap_scores(cat_llm_norm, cat_heuristic, opts)
    if overlap_llm > overlap_heur_weighted:
        logger.info(
            "Conflict: LLM=%s, Heuristic=%s. Overlap favors LLM (%d vs %.2f).",
            cat_llm_norm,
            cat_heuristic,
            overlap_llm,
            overlap_heur_weighted,
        )
        _log_category_conflict("llm", cat_llm_norm, cat_heuristic)
        return cat_llm_norm
    if overlap_heur_weighted > overlap_llm:
        logger.info(
            "Conflict: LLM=%s, Heur=%s. Overlap favors heuristic (%.2f vs %d).",
            cat_llm_norm,
            cat_heuristic,
            overlap_heur_weighted,
            overlap_llm,
        )
        _log_category_conflict("heuristic", cat_llm_norm, cat_heuristic)
        return cat_heuristic
    logger.info("Conflict: LLM=%s, Heuristic=%s. Overlap tie; using heuristic.", cat_llm_norm, cat_heuristic)
    _log_category_conflict("heuristic", cat_llm_norm, cat_heuristic)
    return cat_heuristic


def _weighted_overlap_scores(
    cat_llm_norm: str,
    cat_heuristic: str,
    opts: CategoryCombineOptions,
) -> tuple[int, float]:
    """Return LLM overlap and confidence-weighted heuristic overlap."""
    ctx_tokens = _tokenize_for_overlap(opts.context_for_overlap or "")
    overlap_llm = _overlap_count(_tokenize_for_overlap(cat_llm_norm), ctx_tokens)
    overlap_heur = _overlap_count(_tokenize_for_overlap(cat_heuristic), ctx_tokens)
    score_bonus = _heuristic_score_bonus(opts.heuristic_score, opts.params.heuristic_score_weight)
    return overlap_llm, overlap_heur + score_bonus


def _heuristic_score_bonus(heuristic_score: float | None, heuristic_score_weight: float) -> float:
    """Convert heuristic confidence into an overlap-score bonus."""
    if heuristic_score_weight <= 0 or heuristic_score is None:
        return 0.0
    return heuristic_score_weight * heuristic_score


def _preference_conflict_pick(cat_llm_norm: str, cat_heuristic: str, prefer_llm: bool) -> str:
    """Resolve a category conflict using the configured preference."""
    chosen = "llm" if prefer_llm else "heuristic"
    if prefer_llm:
        logger.info("Conflict: LLM category=%s, Heuristic=%s. Preferring LLM.", cat_llm_norm, cat_heuristic)
        _log_category_conflict(chosen, cat_llm_norm, cat_heuristic)
        return cat_llm_norm
    logger.info("Conflict: LLM category=%s, Heuristic=%s. Prioritizing heuristic.", cat_llm_norm, cat_heuristic)
    _log_category_conflict(chosen, cat_llm_norm, cat_heuristic)
    return cat_heuristic


def _log_category_conflict(
    chosen: str,
    cat_llm_norm: str,
    cat_heuristic: str,
    *,
    detail: str | None = None,
) -> None:
    """Log category conflict to make the resolution decision observable."""
    chosen_label = f"{chosen} ({detail})" if detail else chosen
    logger.info("CategoryConflict chosen=%s llm=%s heuristic=%s", chosen_label, cat_llm_norm, cat_heuristic)


def combine_categories(
    cat_llm: str,
    cat_heur: str,
    options: CategoryCombineOptions | None = None,
) -> str:
    """Merge heuristic and LLM categories using configurable conflict resolution, parent matching, and overlap."""
    opts = options or CategoryCombineOptions()
    cat_llm_norm = normalize_llm_category(cat_llm)
    early_result = _combine_early_result(cat_llm_norm, cat_heur, opts.heuristic_score, opts.params)
    if early_result is not None:
        return early_result

    override = _combine_apply_heuristic_override(cat_heur, cat_llm_norm, opts)
    if override is not None:
        return override
    agreed = _combine_agreement_or_parent(cat_llm_norm, cat_heur, opts.category_parent_map)
    if agreed is not None:
        return agreed
    return _combine_resolve_conflict(cat_llm_norm, cat_heur, opts)


def _is_valid_llm_category(cat_llm_norm: str) -> bool:
    """Return whether an LLM category is specific and usable."""
    return bool(cat_llm_norm) and cat_llm_norm not in PLACEHOLDER_CATEGORIES


def _combine_early_result(
    cat_llm_norm: str,
    cat_heur: str,
    heuristic_score: float | None,
    params: CategoryCombineParams,
) -> str | None:
    """Combine early result without discarding deterministic signals."""
    if cat_heur == "unknown":
        return cat_llm_norm if _is_valid_llm_category(cat_llm_norm) else cat_heur
    if heuristic_score is not None and heuristic_score < params.min_heuristic_score:
        return _low_score_category_pick(cat_llm_norm, cat_heur, heuristic_score, params.min_heuristic_score)
    if not _is_valid_llm_category(cat_llm_norm):
        return cat_heur
    return None


def _low_score_category_pick(
    cat_llm_norm: str,
    cat_heur: str,
    heuristic_score: float,
    min_heuristic_score: float,
) -> str:
    """Prefer a valid LLM category when heuristic confidence is too low."""
    if _is_valid_llm_category(cat_llm_norm):
        logger.info(
            "Heuristic score %.2f below threshold %.2f. Preferring LLM category %s.",
            heuristic_score,
            min_heuristic_score,
            cat_llm_norm,
        )
        return cat_llm_norm
    logger.info(
        "Heuristic score %.2f below threshold %.2f but LLM category is invalid (%s). Using heuristic.",
        heuristic_score,
        min_heuristic_score,
        cat_llm_norm,
    )
    return cat_heur
