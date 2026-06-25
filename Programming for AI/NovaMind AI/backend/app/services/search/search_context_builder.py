"""
LLM context construction layer.

Converts a RankingOutput into a SearchContext object containing a
formatted, token-budgeted text block ready to be injected into an
NVIDIA NIM prompt. No citations are generated here — source references
are preserved as metadata so citation_builder.py (Batch 11b) can inject
them into the assembled answer text.

Token budgeting uses a conservative character-per-token approximation
(4 chars ≈ 1 token) rather than a real tokeniser, which would require
a provider-specific dependency. This approximation is intentionally
slightly conservative so the actual token count never meaningfully
exceeds the budget for any realistic input.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.constants import (
    SEARCH_MODE_CONTEXT_TOKEN_BUDGET,
    SEARCH_MODE_SOURCE_COUNT,
    SearchMode,
)
from app.services.search.query_analyzer import QueryAnalysis, QueryIntent
from app.services.search.ranker import RankedSearchResult, RankingOutput

# Characters-per-token approximation used for budget calculations.
# GPT-family tokenisers average ~4 chars/token for English prose;
# NVIDIA NIM models use comparable tokenisers.
_CHARS_PER_TOKEN: int = 4

# The per-source header template added before each source's snippet.
# The placeholder {n} is the 1-based source reference index used by
# citation_builder.py, not a Python format placeholder.
_SOURCE_HEADER_TEMPLATE = "Source [{n}] — {title} ({domain}):\n"

# Minimum snippet character length to include a source at all.
# Sources with shorter (or empty) snippets provide no useful context
# to the LLM and inflate the token budget without adding value.
_MIN_SNIPPET_LENGTH_TO_INCLUDE: int = 20

# System-level instructions prepended to the context block, per search
# mode. These are terse by design — they consume tokens that should
# mostly go to source content.
_MODE_INSTRUCTIONS: dict[str, str] = {
    SearchMode.NORMAL.value: (
        "Answer the user's question directly using the sources below. "
        "Cite sources inline as [1], [2], etc."
    ),
    SearchMode.RESEARCH.value: (
        "Provide a comprehensive, structured answer using all sources below. "
        "Compare information across sources. Cite all claims inline as [1], [2], etc. "
        "Highlight any conflicting information between sources."
    ),
    SearchMode.DEEP_RESEARCH.value: (
        "Synthesise a thorough, long-form analysis from the sources below. "
        "Structure your answer with clear sections. Cite every factual claim as [1], [2], etc. "
        "Note uncertainty or gaps in source coverage explicitly."
    ),
    SearchMode.ACADEMIC.value: (
        "Provide a precise, evidence-based answer using the sources below. "
        "Prefer information from academic, government, or authoritative sources. "
        "Cite all claims as [1], [2], etc. Note the strength of evidence for key claims."
    ),
    SearchMode.TECHNICAL.value: (
        "Provide a technically precise answer using the sources below. "
        "Include code, configuration, or command-line examples where relevant. "
        "Cite sources as [1], [2], etc."
    ),
}
_DEFAULT_INSTRUCTION = _MODE_INSTRUCTIONS[SearchMode.NORMAL.value]


@dataclass(frozen=True, slots=True)
class IncludedSource:
    """Metadata for a single source included in the context block.
    Passed to citation_builder.py to generate inline citation badges."""

    reference_index: int
    title: str
    url: str
    domain: str
    snippet_used: str
    rank: int
    composite_score: float
    provider: str
    truncated: bool


@dataclass(frozen=True, slots=True)
class TruncationStats:
    """Observability record describing how the context was truncated."""

    sources_available: int
    sources_included: int
    sources_excluded_no_snippet: int
    sources_excluded_budget: int
    total_chars: int
    estimated_tokens: int
    budget_tokens: int
    budget_exhausted: bool


@dataclass(frozen=True, slots=True)
class SearchContext:
    """
    Complete, LLM-ready context block produced by the context builder.
    The context_text field is injected directly into the NVIDIA NIM
    prompt; included_sources is passed to citation_builder.py.
    """

    context_text: str
    included_sources: list[IncludedSource] = field(default_factory=list)
    truncation_stats: TruncationStats = field(
        default_factory=lambda: TruncationStats(0, 0, 0, 0, 0, 0, 0, False)
    )
    search_mode: str = SearchMode.NORMAL.value
    query: str = ""


def _chars_to_tokens(char_count: int) -> int:
    return max(0, char_count // _CHARS_PER_TOKEN)


def _tokens_to_chars(token_count: int) -> int:
    return token_count * _CHARS_PER_TOKEN


def _resolve_search_mode(analysis: QueryAnalysis) -> str:
    return analysis.suggested_search_mode


def _resolve_source_limit(search_mode: str) -> int:
    return SEARCH_MODE_SOURCE_COUNT.get(search_mode, SEARCH_MODE_SOURCE_COUNT[SearchMode.NORMAL.value])


def _resolve_token_budget(search_mode: str) -> int:
    return SEARCH_MODE_CONTEXT_TOKEN_BUDGET.get(
        search_mode, SEARCH_MODE_CONTEXT_TOKEN_BUDGET[SearchMode.NORMAL.value]
    )


def _truncate_snippet(snippet: str, max_chars: int) -> tuple[str, bool]:
    """Truncates a snippet to at most max_chars characters, appending
    an ellipsis when truncation occurs. Returns (text, was_truncated)."""
    if len(snippet) <= max_chars:
        return snippet, False
    truncated = snippet[:max_chars].rsplit(" ", 1)[0]
    return truncated + "…", True


def build_search_context(
    ranking_output: RankingOutput,
    analysis: QueryAnalysis,
) -> SearchContext:
    """
    Constructs a token-budgeted, LLM-ready context block from a
    RankingOutput and the corresponding QueryAnalysis. Synchronous —
    context construction is pure text manipulation with no I/O.

    Sources are included in rank order (best first) until the token
    budget or the per-mode source limit is exhausted, whichever comes
    first. Sources with snippets shorter than _MIN_SNIPPET_LENGTH_TO_INCLUDE
    are excluded before budget accounting begins.

    The returned SearchContext.context_text is structured as:

        [instruction line for this search mode]

        Source [1] — Title (domain):
        <snippet text>

        Source [2] — Title (domain):
        <snippet text>

        ...

    Citation_builder.py uses the reference_index values in
    included_sources to map [1], [2], etc. in the generated answer
    back to actual source URLs.
    """
    search_mode = _resolve_search_mode(analysis)
    token_budget = _resolve_token_budget(search_mode)
    source_limit = _resolve_source_limit(search_mode)
    instruction = _MODE_INSTRUCTIONS.get(search_mode, _DEFAULT_INSTRUCTION)

    char_budget_total = _tokens_to_chars(token_budget)
    instruction_chars = len(instruction) + 2
    char_budget_for_sources = char_budget_total - instruction_chars

    ranked = ranking_output.ranked_results

    usable: list[RankedSearchResult] = []
    excluded_no_snippet = 0
    for ranked_result in ranked:
        if len(ranked_result.result.snippet.strip()) < _MIN_SNIPPET_LENGTH_TO_INCLUDE:
            excluded_no_snippet += 1
            continue
        usable.append(ranked_result)

    included_sources: list[IncludedSource] = []
    context_parts: list[str] = []
    chars_used = 0
    excluded_budget = 0
    budget_exhausted = False

    for ranked_result in usable:
        if len(included_sources) >= source_limit:
            excluded_budget += len(usable) - len(included_sources) - excluded_budget
            break

        result = ranked_result.result
        ref_index = len(included_sources) + 1

        header = _SOURCE_HEADER_TEMPLATE.format(
            n=ref_index,
            title=result.title,
            domain=result.domain,
        )
        header_chars = len(header)
        separator_chars = 2

        remaining_chars = char_budget_for_sources - chars_used - header_chars - separator_chars

        if remaining_chars <= 0:
            budget_exhausted = True
            excluded_budget += 1
            continue

        snippet, was_truncated = _truncate_snippet(result.snippet, remaining_chars)
        block = f"{header}{snippet}\n\n"
        block_chars = len(block)

        if chars_used + block_chars > char_budget_for_sources:
            available = char_budget_for_sources - chars_used - header_chars - 4
            if available < _MIN_SNIPPET_LENGTH_TO_INCLUDE:
                budget_exhausted = True
                excluded_budget += 1
                continue
            snippet, was_truncated = _truncate_snippet(result.snippet, available)
            block = f"{header}{snippet}\n\n"
            block_chars = len(block)
            budget_exhausted = True

        context_parts.append(block)
        chars_used += block_chars

        included_sources.append(
            IncludedSource(
                reference_index=ref_index,
                title=result.title,
                url=result.url,
                domain=result.domain,
                snippet_used=snippet,
                rank=ranked_result.rank,
                composite_score=ranked_result.composite_score,
                provider=result.provider,
                truncated=was_truncated,
            )
        )

    context_text = instruction + "\n\n" + "".join(context_parts)

    total_chars = len(context_text)
    estimated_tokens = _chars_to_tokens(total_chars)

    truncation_stats = TruncationStats(
        sources_available=len(ranked),
        sources_included=len(included_sources),
        sources_excluded_no_snippet=excluded_no_snippet,
        sources_excluded_budget=excluded_budget,
        total_chars=total_chars,
        estimated_tokens=estimated_tokens,
        budget_tokens=token_budget,
        budget_exhausted=budget_exhausted,
    )

    return SearchContext(
        context_text=context_text,
        included_sources=included_sources,
        truncation_stats=truncation_stats,
        search_mode=search_mode,
        query=analysis.original_query,
    )