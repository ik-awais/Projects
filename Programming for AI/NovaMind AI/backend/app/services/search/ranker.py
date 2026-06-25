"""
Search result ranking layer.

Accepts deduplicated SearchResult objects from source_deduplicator.py
and produces deterministically ordered RankedSearchResult objects
suitable for search_context_builder.py. No LLM calls, no citation
generation, no context construction — pure scoring and ordering.

Ranking is a weighted combination of four independent signals:
  1. provider_confidence  — how trustworthy this provider's results are
  2. domain_authority     — TLD/domain quality heuristic
  3. position_score       — provider's own ranking signal (already 0-1)
  4. content_richness     — snippet length as a proxy for result quality

All four signals are normalised to 0.0-1.0 before weighting so no
single signal can dominate through scale differences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.constants import (
    DEFAULT_DOMAIN_SCORE,
    HIGH_AUTHORITY_DOMAIN_SCORE,
    HIGH_AUTHORITY_TLDS,
    SOURCE_RANK_WEIGHT_AUTHORITY,
    SOURCE_RANK_WEIGHT_RECENCY,
    SOURCE_RANK_WEIGHT_RELEVANCE,
    SearchMode,
)
from app.services.providers.base import SearchResult
from app.services.search.query_analyzer import QueryAnalysis, QueryIntent

# Provider confidence scores reflect the relative reliability of each
# configured provider's ranking signal. These are intentionally not
# imported from constants.py because they encode a relationship between
# two specific service layers (providers ↔ ranker) that does not belong
# in the shared constants namespace.
_PROVIDER_CONFIDENCE: dict[str, float] = {
    "tavily": 0.90,
    "firecrawl": 0.80,
}
_DEFAULT_PROVIDER_CONFIDENCE: float = 0.70

# Snippet length boundaries for content-richness normalisation.
# Results with snippets at or above _RICH_SNIPPET_LENGTH get a score of
# 1.0; empty snippets get 0.0; anything in between scales linearly.
_RICH_SNIPPET_LENGTH: int = 200
_EMPTY_SNIPPET_LENGTH: int = 0

# Intent-to-weight overrides allow the ranker to up-weight domain
# authority for academic/research queries and up-weight provider
# confidence for news queries where freshness matters more.
_INTENT_WEIGHT_OVERRIDES: dict[QueryIntent, dict[str, float]] = {
    QueryIntent.RESEARCH: {
        "authority": 0.50,
        "confidence": 0.25,
        "position": 0.15,
        "richness": 0.10,
    },
    QueryIntent.NEWS: {
        "authority": 0.20,
        "confidence": 0.50,
        "position": 0.20,
        "richness": 0.10,
    },
    QueryIntent.COMPARISON: {
        "authority": 0.30,
        "confidence": 0.30,
        "position": 0.20,
        "richness": 0.20,
    },
    QueryIntent.FACTUAL: {
        "authority": 0.35,
        "confidence": 0.35,
        "position": 0.20,
        "richness": 0.10,
    },
    QueryIntent.CONVERSATIONAL: {
        "authority": 0.25,
        "confidence": 0.40,
        "position": 0.25,
        "richness": 0.10,
    },
}
_DEFAULT_WEIGHTS: dict[str, float] = {
    "authority": SOURCE_RANK_WEIGHT_AUTHORITY,
    "confidence": SOURCE_RANK_WEIGHT_RELEVANCE,
    "position": SOURCE_RANK_WEIGHT_RECENCY,
    "richness": 1.0 - SOURCE_RANK_WEIGHT_AUTHORITY - SOURCE_RANK_WEIGHT_RELEVANCE - SOURCE_RANK_WEIGHT_RECENCY,
}


@dataclass(frozen=True, slots=True)
class RankingSignals:
    """Individual signal scores before weighting, preserved for
    observability and debugging."""

    provider_confidence: float
    domain_authority: float
    position_score: float
    content_richness: float


@dataclass(frozen=True, slots=True)
class RankedSearchResult:
    """
    A SearchResult augmented with an explicit composite ranking score
    and the individual signals that produced it. Passed to
    search_context_builder.py in rank-descending order.
    """

    result: SearchResult
    rank: int
    composite_score: float
    signals: RankingSignals
    ranking_reason: str


@dataclass(frozen=True, slots=True)
class RankingOutput:
    """Complete output of a single ranking pass."""

    query: str
    intent: QueryIntent
    ranked_results: list[RankedSearchResult] = field(default_factory=list)
    weights_used: dict[str, float] = field(default_factory=dict)


def _score_domain_authority(domain: str) -> float:
    domain_lower = domain.lower()
    for tld in HIGH_AUTHORITY_TLDS:
        if domain_lower.endswith(tld):
            return HIGH_AUTHORITY_DOMAIN_SCORE
    return DEFAULT_DOMAIN_SCORE


def _score_provider_confidence(provider: str) -> float:
    return _PROVIDER_CONFIDENCE.get(provider.lower(), _DEFAULT_PROVIDER_CONFIDENCE)


def _score_content_richness(snippet: str) -> float:
    length = len(snippet.strip())
    if length <= _EMPTY_SNIPPET_LENGTH:
        return 0.0
    if length >= _RICH_SNIPPET_LENGTH:
        return 1.0
    return length / _RICH_SNIPPET_LENGTH


def _resolve_weights(intent: QueryIntent) -> dict[str, float]:
    return _INTENT_WEIGHT_OVERRIDES.get(intent, _DEFAULT_WEIGHTS)


def _compute_composite_score(
    signals: RankingSignals,
    weights: dict[str, float],
) -> float:
    raw = (
        weights["confidence"] * signals.provider_confidence
        + weights["authority"] * signals.domain_authority
        + weights["position"] * signals.position_score
        + weights["richness"] * signals.content_richness
    )
    return round(min(1.0, max(0.0, raw)), 6)


def _build_ranking_reason(
    signals: RankingSignals,
    weights: dict[str, float],
    intent: QueryIntent,
) -> str:
    dominant_signal = max(
        [
            ("provider_confidence", weights["confidence"] * signals.provider_confidence),
            ("domain_authority", weights["authority"] * signals.domain_authority),
            ("position_score", weights["position"] * signals.position_score),
            ("content_richness", weights["richness"] * signals.content_richness),
        ],
        key=lambda pair: pair[1],
    )[0]
    return (
        f"intent={intent.value} dominant_signal={dominant_signal} "
        f"conf={signals.provider_confidence:.2f} "
        f"auth={signals.domain_authority:.2f} "
        f"pos={signals.position_score:.2f} "
        f"rich={signals.content_richness:.2f}"
    )


def rank_results(
    results: list[SearchResult],
    analysis: QueryAnalysis,
) -> RankingOutput:
    """
    Ranks a list of deduplicated SearchResult objects for a given query
    analysis. Synchronous — ranking is pure computation with no I/O.

    Sorting is stable: results with identical composite scores preserve
    their input order, which reflects first-seen position from
    source_deduplicator.py (itself stable). This guarantees deterministic
    output for the same inputs.

    Returns a RankingOutput with results sorted by composite_score
    descending, each annotated with its rank (1-based), individual
    signals, and a human-readable ranking_reason string.
    """
    if not results:
        return RankingOutput(
            query=analysis.original_query,
            intent=analysis.intent,
            ranked_results=[],
            weights_used=_resolve_weights(analysis.intent),
        )

    weights = _resolve_weights(analysis.intent)

    scored: list[tuple[float, int, SearchResult, RankingSignals]] = []
    for original_index, result in enumerate(results):
        signals = RankingSignals(
            provider_confidence=_score_provider_confidence(result.provider),
            domain_authority=_score_domain_authority(result.domain),
            position_score=float(result.score),
            content_richness=_score_content_richness(result.snippet),
        )
        composite = _compute_composite_score(signals, weights)
        scored.append((composite, original_index, result, signals))

    # Sort descending by composite_score, with original_index as a
    # tie-breaker (ascending) to guarantee stable, deterministic ordering.
    scored.sort(key=lambda item: (-item[0], item[1]))

    ranked: list[RankedSearchResult] = []
    for rank_position, (composite, _, result, signals) in enumerate(scored, start=1):
        ranked.append(
            RankedSearchResult(
                result=result,
                rank=rank_position,
                composite_score=composite,
                signals=signals,
                ranking_reason=_build_ranking_reason(signals, weights, analysis.intent),
            )
        )

    return RankingOutput(
        query=analysis.original_query,
        intent=analysis.intent,
        ranked_results=ranked,
        weights_used=weights,
    )