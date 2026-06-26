"""
Search API router.

Translates HTTP requests into pipeline calls and HTTP responses.
All search logic, ranking, formatting, and caching is delegated
to pipeline.py — this router contains no business logic.

Two endpoints are exposed:

  POST /search          Non-streaming. Returns a complete SearchResponse.
  POST /search/stream   Streaming. Returns an SSE stream of pipeline chunks.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db_session
from app.constants import SSEEvent
from app.core.logging import get_logger
from app.exceptions import (
    AllSearchProvidersFailedError,
    LLMError,
    NoSearchResultsError,
    NovaMindError,
    RateLimitExceededError,
)
from app.models.user import User
from app.schemas.search import (
    CitationMetadataSchema,
    CitationSchema,
    LatencySchema,
    SearchRequest,
    SearchResponse,
    SourceSchema,
)
from app.services.cache_service import CacheService
from app.services.llm.nvidia import NvidiaLLMProvider
from app.services.providers.firecrawl import FirecrawlSearchProvider
from app.services.providers.tavily import TavilySearchProvider
from app.services.search.pipeline import (
    PipelineConfig,
    PipelineResult,
    run_pipeline,
    run_pipeline_streaming,
)
from app.services.search.search_router import SearchRouter

logger = get_logger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

# ── Shared provider / LLM instances ───────────────────────────────────────
# These are module-level singletons. In a future batch these will move
# into FastAPI lifespan state; for now a module-level construction is
# sufficient and avoids per-request re-initialisation.

_search_router = SearchRouter(
    providers={
        "tavily": TavilySearchProvider(),
        "firecrawl": FirecrawlSearchProvider(),
    }
)
_llm_provider = NvidiaLLMProvider()
_cache = CacheService()


# ── Helpers ────────────────────────────────────────────────────────────────

def _pipeline_config_from_request(req: SearchRequest) -> PipelineConfig:
    return PipelineConfig(
        model=req.model,
        max_tokens=req.max_tokens,
        temperature=0.3,
        use_cache=req.use_cache,
        search_mode_override=req.search_mode,
    )


def _build_search_response(result: PipelineResult) -> SearchResponse:
    """Converts a PipelineResult into a SearchResponse schema."""
    formatted = result.formatted_answer
    context = result.search_context

    sources = [
        SourceSchema(
            reference_index=src.reference_index,
            title=src.title,
            url=src.url,
            domain=src.domain,
            provider=src.provider,
            rank=src.rank,
            composite_score=src.composite_score,
        )
        for src in context.included_sources
    ]

    citations = [
        CitationSchema(
            number=ref.number,
            title=ref.title,
            url=ref.url,
            domain=ref.domain,
            provider=ref.provider,
        )
        for ref in formatted.citations_used
    ]

    citation_metadata = None
    if formatted.citation_metadata is not None:
        cm = formatted.citation_metadata
        citation_metadata = CitationMetadataSchema(
            total_sources=cm.total_sources,
            cited_count=cm.cited_count,
            uncited_count=cm.uncited_count,
            citation_numbers=cm.citation_numbers,
        )

    return SearchResponse(
        query=result.query,
        answer=formatted.display_text,
        has_citations=formatted.has_citations,
        sources=sources,
        citations=citations,
        citation_metadata=citation_metadata,
        search_mode=context.search_mode,
        cache_hit=result.cache_hit,
        latency=LatencySchema(
            total_ms=result.total_latency_ms,
            stages=result.stage_latencies_ms,
        ),
    )


async def _sse_event(event: str, data: dict | str) -> str:
    """Formats a single SSE event string."""
    payload = data if isinstance(data, str) else json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n"


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=SearchResponse,
    summary="Execute a search query",
    description=(
        "Runs the full NovaMind search pipeline: web search, ranking, "
        "LLM synthesis, and citation formatting. Returns a complete answer "
        "with cited sources."
    ),
)
async def search(
    request: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> SearchResponse:
    """Non-streaming search endpoint.

    Args:
        request: Validated search request payload.
        current_user: Authenticated user from JWT dependency.
        db: Async database session (available for future conversation
            persistence without changing this signature).

    Returns:
        Complete SearchResponse with answer, sources, and citations.

    Raises:
        NovaMindError subclasses mapped to HTTP status by main.py's
        global exception handler.
    """
    logger.info(
        "Search request received",
        extra={
            "user_id": str(current_user.id),
            "query_length": len(request.query),
            "model": request.model,
            "use_cache": request.use_cache,
        },
    )

    config = _pipeline_config_from_request(request)
    result = await run_pipeline(
        query=request.query,
        router=_search_router,
        llm_provider=_llm_provider,
        cache=_cache,
        config=config,
    )

    logger.info(
        "Search request completed",
        extra={
            "user_id": str(current_user.id),
            "cache_hit": result.cache_hit,
            "total_latency_ms": result.total_latency_ms,
            "citations_used": len(result.formatted_answer.citations_used),
        },
    )

    return _build_search_response(result)


@router.post(
    "/stream",
    summary="Execute a streaming search query",
    description=(
        "Runs the full NovaMind search pipeline and streams the response "
        "as Server-Sent Events. Events are emitted in this order: "
        "sources → token (repeated) → citation (repeated) → done."
    ),
    response_class=StreamingResponse,
)
async def search_stream(
    request: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Streaming search endpoint using Server-Sent Events.

    Args:
        request: Validated search request payload.
        current_user: Authenticated user from JWT dependency.
        db: Async database session.

    Returns:
        StreamingResponse carrying SSE-formatted pipeline chunks.
    """
    logger.info(
        "Streaming search request received",
        extra={
            "user_id": str(current_user.id),
            "query_length": len(request.query),
            "model": request.model,
        },
    )

    config = _pipeline_config_from_request(request)

    async def _event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in run_pipeline_streaming(
                query=request.query,
                router=_search_router,
                llm_provider=_llm_provider,
                cache=_cache,
                config=config,
            ):
                yield await _sse_event(chunk.event_type, chunk.data)
        except NovaMindError as exc:
            yield await _sse_event(
                SSEEvent.ERROR.value,
                {"error": exc.error_code, "message": exc.message},
            )
        except Exception as exc:
            logger.error(
                "Unhandled error in streaming pipeline",
                extra={"exception_type": type(exc).__name__},
                exc_info=exc,
            )
            yield await _sse_event(
                SSEEvent.ERROR.value,
                {"error": "internal_error", "message": "An unexpected error occurred."},
            )

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )