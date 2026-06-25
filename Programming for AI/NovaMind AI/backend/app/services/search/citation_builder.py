"""
Citation mapping layer.

Builds a CitationMap from a SearchContext, providing deterministic
source-number → source-metadata lookup used by answer_formatter.py
to validate and resolve inline citations in the NVIDIA-generated answer.

Citation numbers are read from SearchContext.included_sources directly
(assigned by search_context_builder.py) and are never re-assigned here.
This guarantees the number the LLM received in its prompt matches the
number that appears in its answer and the number the frontend renders.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.search.search_context_builder import IncludedSource, SearchContext

# Pattern that matches citation markers in LLM output, e.g. [1], [12].
# Anchored to avoid matching unrelated bracket content like [code blocks].
CITATION_PATTERN: re.Pattern[str] = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True, slots=True)
class CitationReference:
    """
    The resolved metadata for a single citation number. Passed to the
    frontend so it can render source badges and link previews.
    """

    number: int
    title: str
    url: str
    domain: str
    provider: str
    rank: int
    composite_score: float
    snippet: str


@dataclass(frozen=True, slots=True)
class CitationMetadata:
    """
    Summary of all citations available from a single search context,
    stored alongside the conversation message for future reference.
    """

    total_sources: int
    cited_count: int
    uncited_count: int
    citation_numbers: list[int] = field(default_factory=list)


class CitationMap:
    """
    Bidirectional lookup structure mapping citation numbers ↔ source
    metadata. Constructed once per search context and passed through the
    pipeline immutably after construction.

    Provides:
      - O(1) lookup by citation number (is_valid_citation, resolve)
      - ordered iteration over all available citations
      - tracking of which citations were actually used in an answer
    """

    def __init__(self, included_sources: list[IncludedSource]) -> None:
        self._references: dict[int, CitationReference] = {}
        self._ordered_numbers: list[int] = []

        for source in included_sources:
            ref = CitationReference(
                number=source.reference_index,
                title=source.title,
                url=source.url,
                domain=source.domain,
                provider=source.provider,
                rank=source.rank,
                composite_score=source.composite_score,
                snippet=source.snippet_used,
            )
            self._references[source.reference_index] = ref
            self._ordered_numbers.append(source.reference_index)

    def is_valid_citation(self, number: int) -> bool:
        """Returns True if the citation number exists in this context."""
        return number in self._references

    def resolve(self, number: int) -> CitationReference | None:
        """Returns the CitationReference for a number, or None if invalid."""
        return self._references.get(number)

    def resolve_all(self) -> list[CitationReference]:
        """Returns all citations in rank order."""
        return [self._references[n] for n in self._ordered_numbers]

    def max_valid_number(self) -> int:
        """Returns the highest valid citation number in this map."""
        return max(self._ordered_numbers) if self._ordered_numbers else 0

    def size(self) -> int:
        return len(self._references)

    def compute_metadata(self, cited_numbers: set[int]) -> CitationMetadata:
        valid_cited = {n for n in cited_numbers if self.is_valid_citation(n)}
        uncited = self.size() - len(valid_cited)
        return CitationMetadata(
            total_sources=self.size(),
            cited_count=len(valid_cited),
            uncited_count=uncited,
            citation_numbers=sorted(valid_cited),
        )


def build_citation_map(context: SearchContext) -> CitationMap:
    """
    Constructs a CitationMap from a SearchContext. The returned map is
    the single source of truth for citation number → source metadata
    for the remainder of the pipeline.
    """
    return CitationMap(context.included_sources)


def extract_citation_numbers(text: str) -> list[int]:
    """
    Extracts all citation numbers from a text string in order of
    appearance. May contain duplicates — deduplication is the
    responsibility of answer_formatter.py, not this layer.
    """
    return [int(m) for m in CITATION_PATTERN.findall(text)]


def validate_citations(
    text: str,
    citation_map: CitationMap,
) -> tuple[list[int], list[int]]:
    """
    Splits all citation numbers found in text into two lists:
      - valid:   numbers that exist in the citation map
      - invalid: numbers that do not exist in the citation map
                 (hallucinated by the model or referencing a source
                 that was excluded from context by the token budget)
    Returns (valid_numbers, invalid_numbers), each in appearance order.
    """
    all_numbers = extract_citation_numbers(text)
    valid = [n for n in all_numbers if citation_map.is_valid_citation(n)]
    invalid = [n for n in all_numbers if not citation_map.is_valid_citation(n)]
    return valid, invalid