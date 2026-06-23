"""
Source deduplication layer.

Removes duplicate search results by normalized URL across one or more
provider responses, preserving the highest-quality (highest score)
instance of each duplicate and maintaining stable, deterministic output
ordering. Contains no ranking logic beyond the tie-breaking needed to
choose which duplicate to keep.
"""

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from app.services.providers.base import SearchResult

_TRACKING_QUERY_PREFIXES: tuple[str, ...] = ("utm_", "ref", "fbclid", "gclid", "mc_cid", "mc_eid")


@dataclass(frozen=True, slots=True)
class DeduplicationStats:
    """Observability record describing what the deduplication pass did."""

    input_count: int
    output_count: int
    duplicates_removed: int


def _normalize_url(url: str) -> str:
    """
    Normalizes a URL for comparison purposes only (not for display or
    storage): lowercases the scheme/host, strips a trailing slash, drops
    common tracking query parameters, and removes URL fragments.
    """
    parts = urlsplit(url.strip())

    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[len("www."):]

    path = parts.path.rstrip("/") or "/"

    query_pairs = [
        pair
        for pair in parts.query.split("&")
        if pair and not pair.split("=")[0].lower().startswith(_TRACKING_QUERY_PREFIXES)
    ]
    query = "&".join(sorted(query_pairs))

    normalized = urlunsplit((scheme, netloc, path, query, ""))
    return normalized


def _is_higher_quality(candidate: SearchResult, current_best: SearchResult) -> bool:
    """
    Determines whether candidate should replace current_best as the kept
    instance of a duplicate URL. Higher score wins; on an exact score tie,
    the result with the longer (more informative) snippet wins; any
    further tie keeps the existing best, preserving stable ordering.
    """
    if candidate.score != current_best.score:
        return candidate.score > current_best.score
    return len(candidate.snippet) > len(current_best.snippet)


def deduplicate_results(
    results: list[SearchResult],
) -> tuple[list[SearchResult], DeduplicationStats]:
    """
    Removes duplicate results by normalized URL, preserving the
    highest-quality instance of each duplicate. Output order is stable:
    results appear in the position of their FIRST occurrence in the input
    list, regardless of which duplicate instance's data was ultimately
    kept.

    This function is synchronous and side-effect-free — deduplication is
    pure data transformation, not I/O.
    """
    best_by_normalized_url: dict[str, SearchResult] = {}
    first_seen_order: list[str] = []

    for result in results:
        normalized_url = _normalize_url(result.url)

        if normalized_url not in best_by_normalized_url:
            best_by_normalized_url[normalized_url] = result
            first_seen_order.append(normalized_url)
            continue

        current_best = best_by_normalized_url[normalized_url]
        if _is_higher_quality(result, current_best):
            best_by_normalized_url[normalized_url] = result

    deduplicated = [best_by_normalized_url[url] for url in first_seen_order]

    stats = DeduplicationStats(
        input_count=len(results),
        output_count=len(deduplicated),
        duplicates_removed=len(results) - len(deduplicated),
    )

    return deduplicated, stats


def deduplicate_search_responses(
    responses: list,
) -> tuple[list[SearchResult], DeduplicationStats]:
    """
    Convenience entry point for search_router.py's output: flattens a
    list of SearchResponse objects (each carrying its own .results list)
    into a single deduplicated list of SearchResult, preserving the
    provider order in which the responses were passed in.
    """
    all_results: list[SearchResult] = []
    for response in responses:
        all_results.extend(response.results)
    return deduplicate_results(all_results)