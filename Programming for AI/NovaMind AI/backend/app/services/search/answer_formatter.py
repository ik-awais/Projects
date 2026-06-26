"""
Answer formatting layer.

Accepts the raw text produced by NVIDIA NIM and a CitationMap, and
returns a cleaned, validated FormattedAnswer ready for SSE delivery
and frontend rendering. No LLM calls, no retrieval, no re-ranking.

Responsibilities:
  - Normalize whitespace and paragraph structure
  - Remove hallucinated citation numbers not in CitationMap
  - Collapse duplicate citations within the same paragraph
  - Preserve cross-paragraph citation repeats (legitimate references)
  - Produce streaming-compatible output (clean text, no partial state)
  - Never fail on malformed input — always return a usable result
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.search.citation_builder import (
    CITATION_PATTERN,
    CitationMap,
    CitationMetadata,
    CitationReference,
    extract_citation_numbers,
    validate_citations,
)

# Maximum consecutive blank lines collapsed to a single paragraph break.
_MAX_BLANK_LINES: int = 1

# Regex matching two or more whitespace characters that are not newlines,
# used to collapse runs of spaces/tabs within lines.
_INLINE_WHITESPACE_RE: re.Pattern[str] = re.compile(r"[^\S\n]{2,}")

# Regex matching trailing whitespace before a newline.
_TRAILING_SPACE_RE: re.Pattern[str] = re.compile(r"[ \t]+\n")

# Regex matching more than _MAX_BLANK_LINES consecutive blank lines.
_EXCESS_BLANK_LINES_RE: re.Pattern[str] = re.compile(r"\n{3,}")

# A citation cluster is two or more citation markers with only whitespace
# between them, e.g. "[1] [2] [3]" or "[1][2]". Used to detect and
# deduplicate multi-citation runs.
_CITATION_CLUSTER_RE: re.Pattern[str] = re.compile(
    r"(\[\d+\])(\s*\[\d+\])+"
)


@dataclass(frozen=True, slots=True)
class FormattedAnswer:
    """
    The fully post-processed answer ready for delivery to the frontend
    via SSE or the REST response body.
    """

    display_text: str
    has_citations: bool
    citations_used: list[CitationReference] = field(default_factory=list)
    invalid_citations_removed: list[int] = field(default_factory=list)
    duplicates_collapsed: int = 0
    citation_metadata: CitationMetadata | None = None


@dataclass
class _FormattingContext:
    """Mutable working state during a single formatting pass."""

    paragraphs: list[str] = field(default_factory=list)
    cited_numbers_in_order: list[int] = field(default_factory=list)
    cited_numbers_seen: set[int] = field(default_factory=set)
    invalid_numbers: list[int] = field(default_factory=list)
    duplicates_collapsed: int = 0


def _normalize_whitespace(text: str) -> str:
    """
    Normalizes whitespace in raw LLM output:
      1. Strip trailing spaces before newlines
      2. Collapse inline whitespace runs to single space
      3. Collapse excess blank lines to single paragraph breaks
      4. Strip leading/trailing whitespace from the whole text
    """
    text = _TRAILING_SPACE_RE.sub("\n", text)
    text = _INLINE_WHITESPACE_RE.sub(" ", text)
    text = _EXCESS_BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def _remove_invalid_citations(
    text: str,
    citation_map: CitationMap,
) -> tuple[str, list[int]]:
    """
    Removes citation markers whose numbers do not exist in citation_map
    (hallucinated references). Returns the cleaned text and the list of
    removed numbers, preserving all other content exactly.
    """
    invalid_numbers: list[int] = []

    def _replace(match: re.Match[str]) -> str:
        number = int(match.group(1))
        if citation_map.is_valid_citation(number):
            return match.group(0)
        invalid_numbers.append(number)
        return ""

    cleaned = CITATION_PATTERN.sub(_replace, text)
    cleaned = _INLINE_WHITESPACE_RE.sub(" ", cleaned)
    return cleaned, invalid_numbers


def _collapse_duplicate_citations_in_paragraph(
    paragraph: str,
    seen_in_paragraph: set[int],
) -> tuple[str, int, set[int]]:
    """
    Deduplicates citation markers within a single paragraph. A citation
    number that has already appeared earlier in the same paragraph is
    removed on subsequent occurrences. Returns (cleaned_paragraph,
    count_removed, set_of_numbers_seen_in_this_paragraph).

    Cross-paragraph duplicates are handled by the caller, which resets
    seen_in_paragraph at each paragraph boundary.
    """
    count_removed = 0
    seen_this_para: set[int] = set()

    def _replace(match: re.Match[str]) -> str:
        nonlocal count_removed
        number = int(match.group(1))
        if number in seen_in_paragraph or number in seen_this_para:
            count_removed += 1
            return ""
        seen_this_para.add(number)
        return match.group(0)

    cleaned = CITATION_PATTERN.sub(_replace, paragraph)
    cleaned = _INLINE_WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned, count_removed, seen_this_para


def _process_paragraphs(
    text: str,
    citation_map: CitationMap,
) -> _FormattingContext:
    """
    Processes the whitespace-normalized, invalid-citation-stripped text
    paragraph by paragraph, deduplicating citations within each paragraph
    and tracking all citation numbers that appear in the final output in
    order of first appearance.
    """
    ctx = _FormattingContext()
    paragraphs = text.split("\n\n")

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        seen_in_paragraph: set[int] = set()
        cleaned_para, removed, seen_this_para = _collapse_duplicate_citations_in_paragraph(
            paragraph, seen_in_paragraph
        )
        ctx.duplicates_collapsed += removed

        for number in extract_citation_numbers(cleaned_para):
            if number not in ctx.cited_numbers_seen:
                ctx.cited_numbers_in_order.append(number)
                ctx.cited_numbers_seen.add(number)

        ctx.paragraphs.append(cleaned_para)

    return ctx


def _ensure_citations_at_sentence_end(text: str) -> str:
    """
    Moves citation markers that appear before a period to after it.
    E.g. "[1]." → ".[1]" is wrong; "[1]" after the period is canonical.
    This corrects a common model output pattern where citations land
    just inside sentence-ending punctuation.

    Input:  "pgvector supports HNSW [1]. It also supports IVFFlat."
    Output: "pgvector supports HNSW[1]. It also supports IVFFlat."

    No change is made if the citation already follows punctuation.
    """
    return re.sub(r"\s+(\[\d+\])\.", r"\1.", text)


def format_answer(
    raw_answer: str,
    citation_map: CitationMap,
) -> FormattedAnswer:
    """
    Post-processes a raw NVIDIA NIM answer into a frontend-safe
    FormattedAnswer. The full processing pipeline is:

      1. Guard against empty/None input
      2. Normalize whitespace
      3. Remove hallucinated/invalid citation numbers
      4. Collapse intra-paragraph duplicate citations
      5. Move citations to canonical post-punctuation position
      6. Re-join paragraphs with clean double newlines
      7. Build ordered citation reference list from CitationMap
      8. Compute CitationMetadata

    This function never raises — malformed or empty input always
    produces a usable FormattedAnswer with appropriate flags set.
    """
    if not raw_answer or not raw_answer.strip():
        empty_metadata = citation_map.compute_metadata(set())
        return FormattedAnswer(
            display_text="",
            has_citations=False,
            citations_used=[],
            invalid_citations_removed=[],
            duplicates_collapsed=0,
            citation_metadata=empty_metadata,
        )

    normalized = _normalize_whitespace(raw_answer)
    without_invalid, invalid_numbers = _remove_invalid_citations(normalized, citation_map)

    ctx = _process_paragraphs(without_invalid, citation_map)
    display_text = "\n\n".join(ctx.paragraphs)
    display_text = _ensure_citations_at_sentence_end(display_text)
    display_text = _normalize_whitespace(display_text)

    citations_used: list[CitationReference] = []
    for number in ctx.cited_numbers_in_order:
        ref = citation_map.resolve(number)
        if ref is not None:
            citations_used.append(ref)

    has_citations = len(citations_used) > 0
    citation_metadata = citation_map.compute_metadata(ctx.cited_numbers_seen)

    return FormattedAnswer(
        display_text=display_text,
        has_citations=has_citations,
        citations_used=citations_used,
        invalid_citations_removed=sorted(set(invalid_numbers)),
        duplicates_collapsed=ctx.duplicates_collapsed,
        citation_metadata=citation_metadata,
    )


def format_streaming_chunk(
    chunk_text: str,
    citation_map: CitationMap,
) -> str:
    """
    Lightweight formatter for individual SSE stream chunks. Only removes
    invalid citation numbers — it does not attempt deduplication or
    paragraph normalization, since those operations require the full text
    to be meaningful. The final complete answer is passed through
    format_answer() once the stream is done.

    Returns the cleaned chunk text, which may be empty if the entire
    chunk consisted of an invalid citation marker.
    """
    if not chunk_text:
        return ""

    cleaned, _ = _remove_invalid_citations(chunk_text, citation_map)
    return cleaned