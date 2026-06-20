# backend/app/services/providers/base.py

"""
Search provider abstraction layer.

Defines the provider-independent contract every search provider (Tavily,
Brave, and any future provider) must implement. No provider-specific
logic belongs in this file — it exists so that search_router.py (a future
batch) can call any provider polymorphically without special-casing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SearchResult:
    """
    A single, provider-independent search result. Every provider
    implementation must normalize its raw API response into this exact
    shape — no provider-specific fields are permitted here.
    """

    title: str
    url: str
    domain: str
    snippet: str
    provider: str
    score: float


@dataclass(frozen=True, slots=True)
class SearchResponse:
    """
    The complete, provider-independent response from a single provider
    search call. Wraps a list of SearchResult plus call-level metadata
    useful for ranking, caching, and analytics in later batches.
    """

    provider: str
    query: str
    results: list[SearchResult] = field(default_factory=list)
    total_results: int = 0
    search_time_ms: int = 0


class SearchProvider(ABC):
    """
    Abstract base class every concrete search provider must subclass.
    A provider's only job is: given a query, return a SearchResponse.
    Ranking, deduplication, and aggregation across multiple providers are
    explicitly out of scope here — that belongs to search_router.py.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Stable, lowercase identifier for this provider, e.g. 'tavily'."""
        raise NotImplementedError

    @abstractmethod
    async def search(self, query: str, *, max_results: int = 5) -> SearchResponse:
        """
        Executes a search against this provider and returns a normalized,
        provider-independent SearchResponse.

        Implementations must:
        - Never raise raw HTTP/library exceptions to the caller; wrap
          failures in app.exceptions.SearchProviderError.
        - Never return fewer than zero or more than max_results results.
        - Always populate every field of every SearchResult — no field
          may be left as None, an empty placeholder, or omitted.
        """
        raise NotImplementedError