"""
Search pipeline orchestration.

This module is the single entry point for executing a complete NovaMind
search: it calls the already-verified stages in the correct order and
returns either a complete FormattedAnswer or an async iterator of
streaming chunks.

Responsibilities:
  - Coordinate existing pipeline stages in order
  - Apply result caching via CacheService
  - Surface structured exceptions to callers (API layer)
  - Log stage timings and outcomes for observability
  - Nothing else

Stages called (in order), each implemented in their own verified module:
  1.  query_analyzer     → QueryAnalysis
  2.  search_router      → RoutedSearchResult
  3.  source_deduplicator → deduplicated SearchResult list
  4.  ranker             → RankingOutput
  5.  search_context_builder → SearchContext
  6.  nvidia             → streamed or complete LLM answer
  7.  citation_builder   → CitationMap
  8.  answer_formatter   → FormattedAnswer  (or streaming chunks)
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.constants import (
    CACHE_KEY_PREFIX_SEARCH,
    NVIDIA_MAX_TOKENS_DEFAULT,
    NVIDIA_TEMPERATURE_DEFAULT,
    SEARCH_RESULT_CACHE_TTL_SECONDS,
    NvidiaModel,
    SearchMode,
)
from app.core.logging import get_logger
from app.exceptions import (
    AllSearchProvidersFailedError,
    LLMError,
    NoSearchResultsError,
    SearchError,
)
from app.services.cache_service import CacheService
from app.services.llm.base import LLMMessage, LLMMessageRole
from app.services.llm.nvidia import NvidiaLLMProvider
from app.services.providers.base import SearchProvider
from app.services.search.answer_formatter import (
    FormattedAnswer,
    format_answer,
    format_streaming_chunk,
)
from app.services.search.citation_builder import build_citation_map
from app.services.search.query_analyzer import QueryAnalysis, QueryIntent, analyze_query
from app.services.search.ranker import rank_results
from app.services.search.search_context_builder import SearchContext, build_search_context
from app.services.search.search_router import SearchRouter
from app.services.search.source_deduplicator import deduplicate_search_responses

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """
    Runtime configuration for a single pipeline invocation. Callers
    (the API layer) construct this and pass it to the pipeline functions.
    All fields have production-safe defaults.
    """

    model: str = NvidiaModel.LLAMA_3_3_70B.value
    max_tokens: int = NVIDIA_MAX_TOKENS_DEFAULT
    temperature: float = NVIDIA_TEMPERATURE_DEFAULT
    use_cache: bool = True
    search_mode_override: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """
    Complete, pipeline-produced result for a single search query.
    Returned by run_pipeline() for non-streaming callers.
    """

    query: str
    formatted_answer: FormattedAnswer
    search_context: SearchContext
    analysis: QueryAnalysis
    total_latency_ms: int
    stage_latencies_ms: dict[str, int] = field(default_factory=dict)
    cache_hit: bool = False


@dataclass(frozen=True, slots=True)
class StreamingChunk:
    """
    A single unit of streamed output emitted by run_pipeline_streaming().
    event_type mirrors the SSE event names in constants.SSEEvent so the
    API layer can forward chunks directly without re-interpreting them.
    """

    event_type: str
    data: str | dict


def _make_cache_key(query: str, config: PipelineConfig) -> str:
    """
    Deterministic cache key incorporating the query text and the
    pipeline settings that affect output (model, search_mode_override).
    Temperature is intentionally excluded — it is a sampling parameter
    and does not define a unique logical question.
    """
    raw = f"{query.strip().lower()}|{config.model}|{config.search_mode_override or ''}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{CACHE_KEY_PREFIX_SEARCH}{digest}"


def _build_llm_messages(
    analysis: QueryAnalysis,
    context: SearchContext,
) -> list[LLMMessage]:
    """
    Constructs the message list passed to NvidiaLLMProvider. The system
    message instructs the model to cite sources using the [N] notation
    that citation_builder.py expects; the user message pairs the original
    query with the constructed context block.
    """
    system_content = (
        "You are NovaMind, an expert AI search assistant. "
        "Answer the user's question using only the provided sources. "
        "Cite every factual claim with its source number in square brackets, e.g. [1]. "
        "Do not invent information not present in the sources. "
        "If the sources do not contain enough information to answer, say so explicitly."
    )
    user_content = (
        f"Question: {analysis.original_query}\n\n"
        f"{context.context_text}"
    )
    return [
        LLMMessage(role=LLMMessageRole.SYSTEM, content=system_content),
        LLMMessage(role=LLMMessageRole.USER, content=user_content),
    ]


async def _run_search_stages(
    query: str,
    router: SearchRouter,
    config: PipelineConfig,
) -> tuple[QueryAnalysis, SearchContext, dict[str, int]]:
    """
    Executes the deterministic search stages (analysis → routing →
    deduplication → ranking → context) and returns the QueryAnalysis,
    SearchContext, and a dict of per-stage latencies in milliseconds.

    Separated from the LLM stage so the API layer can use the search
    result independently (e.g. to stream source cards before the answer
    begins streaming).
    """
    latencies: dict[str, int] = {}

    t0 = time.monotonic()
    analysis = await analyze_query(query)
    if config.search_mode_override:
        from dataclasses import replace
        analysis = replace(analysis, suggested_search_mode=config.search_mode_override)
    latencies["query_analysis_ms"] = int((time.monotonic() - t0) * 1000)

    logger.info(
        "Query analyzed",
        extra={
            "query": query,
            "intent": analysis.intent.value,
            "search_mode": analysis.suggested_search_mode,
            "requires_search": analysis.requires_search,
        },
    )

    if not analysis.requires_search or analysis.intent == QueryIntent.CONVERSATIONAL:
        empty_context = SearchContext(
            context_text="",
            included_sources=[],
            search_mode=analysis.suggested_search_mode,
            query=query,
        )
        return analysis, empty_context, latencies

    t1 = time.monotonic()
    routed = await router.route(analysis)
    latencies["search_routing_ms"] = int((time.monotonic() - t1) * 1000)

    logger.info(
        "Search routing complete",
        extra={
            "providers_succeeded": routed.succeeded_provider_count,
            "providers_failed": routed.failed_provider_count,
            "total_raw_results": sum(len(r.results) for r in routed.responses),
        },
    )

    t2 = time.monotonic()
    deduped_results, dedup_stats = deduplicate_search_responses(routed.responses)
    latencies["deduplication_ms"] = int((time.monotonic() - t2) * 1000)

    logger.info(
        "Deduplication complete",
        extra={
            "input_count": dedup_stats.input_count,
            "output_count": dedup_stats.output_count,
            "duplicates_removed": dedup_stats.duplicates_removed,
        },
    )

    if not deduped_results:
        raise NoSearchResultsError(query)

    t3 = time.monotonic()
    ranking_output = rank_results(deduped_results, analysis)
    latencies["ranking_ms"] = int((time.monotonic() - t3) * 1000)

    t4 = time.monotonic()
    context = build_search_context(ranking_output, analysis)
    latencies["context_build_ms"] = int((time.monotonic() - t4) * 1000)

    logger.info(
        "Context built",
        extra={
            "sources_included": context.truncation_stats.sources_included,
            "estimated_tokens": context.truncation_stats.estimated_tokens,
            "budget_exhausted": context.truncation_stats.budget_exhausted,
        },
    )

    return analysis, context, latencies


async def run_pipeline(
    query: str,
    router: SearchRouter,
    llm_provider: NvidiaLLMProvider,
    cache: CacheService,
    config: PipelineConfig | None = None,
) -> PipelineResult:
    """
    Executes the complete search pipeline and returns a PipelineResult.
    Use this for non-streaming callers that need the full answer before
    returning a response.

    Cache behaviour: if use_cache is True and a cached PipelineResult
    exists for this query+config combination, it is returned immediately.
    On a miss, the result is stored in the cache after completion.
    """
    if config is None:
        config = PipelineConfig()

    pipeline_start = time.monotonic()
    cache_key = _make_cache_key(query, config)

    if config.use_cache:
        cached = await cache.get(cache_key)
        if cached is not None:
            logger.info("Cache hit", extra={"query": query})
            return cached

    analysis, context, latencies = await _run_search_stages(query, router, config)

    messages = _build_llm_messages(analysis, context)

    t_llm = time.monotonic()
    completion = await llm_provider.complete(
        messages,
        model=config.model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
    )
    latencies["llm_ms"] = int((time.monotonic() - t_llm) * 1000)

    logger.info(
        "LLM completion received",
        extra={
            "model": config.model,
            "tokens_used": completion.usage.total_tokens,
            "latency_ms": completion.latency_ms,
            "finish_reason": completion.finish_reason,
        },
    )

    citation_map = build_citation_map(context)
    formatted = format_answer(completion.content, citation_map)

    total_ms = int((time.monotonic() - pipeline_start) * 1000)

    result = PipelineResult(
        query=query,
        formatted_answer=formatted,
        search_context=context,
        analysis=analysis,
        total_latency_ms=total_ms,
        stage_latencies_ms=latencies,
        cache_hit=False,
    )

    if config.use_cache:
        await cache.set(cache_key, result, ttl_seconds=SEARCH_RESULT_CACHE_TTL_SECONDS)

    logger.info(
        "Pipeline complete",
        extra={
            "query": query,
            "total_latency_ms": total_ms,
            "citations_used": len(formatted.citations_used),
            "has_citations": formatted.has_citations,
        },
    )

    return result


async def run_pipeline_streaming(
    query: str,
    router: SearchRouter,
    llm_provider: NvidiaLLMProvider,
    cache: CacheService,
    config: PipelineConfig | None = None,
) -> AsyncIterator[StreamingChunk]:
    """
    Executes the search pipeline with streaming LLM output. Yields
    StreamingChunk objects in this sequence:

      1. One "sources" chunk — the included sources list, ready for the
         frontend to render source cards before the answer arrives.
      2. Zero or more "token" chunks — individual answer fragments from
         the NVIDIA stream, with hallucinated citations stripped via
         format_streaming_chunk().
      3. One "done" chunk — follow-up question suggestions and final
         citation metadata.

    The complete assembled answer is also stored in the cache after
    streaming completes (if use_cache=True), so a subsequent non-
    streaming call for the same query returns immediately.
    """
    if config is None:
        config = PipelineConfig()

    import json
    from app.constants import SSEEvent

    pipeline_start = time.monotonic()
    analysis, context, _ = await _run_search_stages(query, router, config)
    citation_map = build_citation_map(context)

    sources_payload = [
        {
            "reference_index": src.reference_index,
            "title": src.title,
            "url": src.url,
            "domain": src.domain,
            "provider": src.provider,
            "rank": src.rank,
            "composite_score": src.composite_score,
        }
        for src in context.included_sources
    ]
    yield StreamingChunk(
        event_type=SSEEvent.SOURCES.value,
        data={"sources": sources_payload, "query": query},
    )

    accumulated_text = ""
    async for chunk in llm_provider.stream(
        _build_llm_messages(analysis, context),
        model=config.model,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
    ):
        if chunk.is_final:
            break
        if chunk.delta:
            clean_delta = format_streaming_chunk(chunk.delta, citation_map)
            if clean_delta:
                accumulated_text += clean_delta
                yield StreamingChunk(
                    event_type=SSEEvent.TOKEN.value,
                    data=clean_delta,
                )

    formatted = format_answer(accumulated_text, citation_map)

    cited_numbers = {ref.number for ref in formatted.citations_used}
    for number in cited_numbers:
        ref = citation_map.resolve(number)
        if ref is not None:
            yield StreamingChunk(
                event_type=SSEEvent.CITATION.value,
                data={
                    "number": number,
                    "url": ref.url,
                    "title": ref.title,
                    "domain": ref.domain,
                },
            )

    total_ms = int((time.monotonic() - pipeline_start) * 1000)

    yield StreamingChunk(
        event_type=SSEEvent.DONE.value,
        data={
            "citations_used": len(formatted.citations_used),
            "has_citations": formatted.has_citations,
            "total_latency_ms": total_ms,
            "search_mode": context.search_mode,
        },
    )

    if config.use_cache:
        cache_key = _make_cache_key(query, config)
        from dataclasses import replace as _replace
        result = PipelineResult(
            query=query,
            formatted_answer=formatted,
            search_context=context,
            analysis=analysis,
            total_latency_ms=total_ms,
            cache_hit=False,
        )
        await cache.set(cache_key, result, ttl_seconds=SEARCH_RESULT_CACHE_TTL_SECONDS)

    logger.info(
        "Streaming pipeline complete",
        extra={
            "query": query,
            "total_latency_ms": total_ms,
            "citations_used": len(formatted.citations_used),
        },
    )