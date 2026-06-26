"""
Pydantic v2 schemas for the search API.

Serialization only — no business logic. All types mirror what
pipeline.py already produces so no translation layer is needed
between pipeline output and HTTP response.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Request ────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    """Request body for POST /search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The user's search query.",
    )
    model: str = Field(
        default="meta/llama-3.3-70b-instruct",
        description="NVIDIA NIM model identifier to use for answer generation.",
    )
    search_mode: str | None = Field(
        default=None,
        description=(
            "Override the auto-detected search mode. "
            "Accepted values: normal, research, deep_research, academic, technical."
        ),
    )
    max_tokens: int = Field(
        default=2048,
        ge=64,
        le=8192,
        description="Maximum tokens for the generated answer.",
    )
    use_cache: bool = Field(
        default=True,
        description="Return a cached result if one exists for this query.",
    )


# ── Source / citation sub-schemas ──────────────────────────────────────────

class SourceSchema(BaseModel):
    """A single ranked source included in the search context."""

    reference_index: int
    title: str
    url: str
    domain: str
    provider: str
    rank: int
    composite_score: float

    model_config = {"from_attributes": True}


class CitationSchema(BaseModel):
    """A single citation resolved from the answer text."""

    number: int
    title: str
    url: str
    domain: str
    provider: str

    model_config = {"from_attributes": True}


class CitationMetadataSchema(BaseModel):
    """Aggregate citation statistics for observability."""

    total_sources: int
    cited_count: int
    uncited_count: int
    citation_numbers: list[int]

    model_config = {"from_attributes": True}


# ── Pipeline latency sub-schema ────────────────────────────────────────────

class LatencySchema(BaseModel):
    """Per-stage and total latency information from the pipeline."""

    total_ms: int
    stages: dict[str, int] = Field(default_factory=dict)


# ── Normal (non-streaming) response ───────────────────────────────────────

class SearchResponse(BaseModel):
    """
    Complete response for POST /search (non-streaming).

    answer is the formatted, citation-cleaned text ready for display.
    sources contains all sources included in the search context.
    citations contains only those sources actually cited in the answer.
    """

    query: str
    answer: str
    has_citations: bool
    sources: list[SourceSchema]
    citations: list[CitationSchema]
    citation_metadata: CitationMetadataSchema | None
    search_mode: str
    cache_hit: bool
    latency: LatencySchema


# ── Streaming metadata schemas ─────────────────────────────────────────────

class StreamingSourcesPayload(BaseModel):
    """
    Payload of the SSE 'sources' event emitted before answer tokens
    begin streaming. Allows the frontend to render source cards
    immediately without waiting for the full answer.
    """

    query: str
    sources: list[SourceSchema]


class StreamingDonePayload(BaseModel):
    """Payload of the SSE 'done' event that closes the stream."""

    citations_used: int
    has_citations: bool
    total_latency_ms: int
    search_mode: str