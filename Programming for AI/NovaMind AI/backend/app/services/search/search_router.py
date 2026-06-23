"""
Search routing layer.

Accepts a QueryAnalysis and routes the search to one or more configured
providers (Tavily, Brave) concurrently, respecting per-provider timeouts
and degrading gracefully if one provider fails. Returns a single,
unified RoutedSearchResult containing the raw, unranked, undeduplicated
results from every provider that succeeded. Ranking, deduplication, and
citation generation are explicitly out of scope here.
"""

import asyncio
from dataclasses import dataclass, field

from app.constants import SearchProviderName
from app.exceptions import AllSearchProvidersFailedError, SearchProviderError
from app.services.search.query_analyzer import QueryAnalysis, QueryIntent
from app.services.providers.base import SearchProvider, SearchResponse

# Depth (1-3, from QueryAnalysis.estimated_depth) maps to a per-provider
# result count. Depth itself is provider-independent; this mapping is the
# router's own concern, not the analyzer's.
_DEPTH_TO_RESULT_COUNT: dict[int, int] = {
    1: 4,
    2: 6,
    3: 10,
}
_DEFAULT_RESULT_COUNT = 4

# Providers preferred for time-sensitive (news) queries are tried first
# and, if at least one succeeds, the router does not need every provider
# to succeed for the overall call to be considered successful.
_NEWS_PREFERRED_PROVIDER_ORDER: tuple[str, ...] = (
    SearchProviderName.TAVILY.value,
    SearchProviderName.FIRECRAWL.value,
)
_DEFAULT_PROVIDER_ORDER: tuple[str, ...] = (
    SearchProviderName.TAVILY.value,
    SearchProviderName.FIRECRAWL.value,
)

@dataclass(frozen=True, slots=True)
class ProviderOutcome:
    """The outcome of a single provider's search attempt, success or
    failure, used for observability and graceful-degradation reporting."""

    provider: str
    succeeded: bool
    response: SearchResponse | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class RoutedSearchResult:
    """
    Unified, provider-independent output of a routed search call.
    Contains the raw, unranked, undeduplicated results from every
    provider that succeeded, plus an outcome record per provider attempted
    so the caller can observe partial failures.
    """

    query: str
    responses: list[SearchResponse] = field(default_factory=list)
    outcomes: list[ProviderOutcome] = field(default_factory=list)

    @property
    def succeeded_provider_count(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.succeeded)

    @property
    def failed_provider_count(self) -> int:
        return sum(1 for outcome in self.outcomes if not outcome.succeeded)


class SearchRouter:
    """
    Routes a QueryAnalysis to one or more SearchProvider instances,
    running them concurrently and tolerating individual provider failures.
    """

    def __init__(self, providers: dict[str, SearchProvider]) -> None:
        """
        providers: a mapping of provider_name -> SearchProvider instance,
        e.g. {"tavily": TavilySearchProvider(), "brave": BraveSearchProvider()}.
        The router itself constructs no provider instances — they are
        injected, so future providers (Exa, etc.) require no change here.
        """
        if not providers:
            raise ValueError("SearchRouter requires at least one configured provider.")
        self._providers = providers

    def _resolve_result_count(self, analysis: QueryAnalysis) -> int:
        return _DEPTH_TO_RESULT_COUNT.get(analysis.estimated_depth, _DEFAULT_RESULT_COUNT)

    def _resolve_provider_order(self, analysis: QueryAnalysis) -> list[str]:
        preferred_order = (
            _NEWS_PREFERRED_PROVIDER_ORDER
            if analysis.is_time_sensitive
            else _DEFAULT_PROVIDER_ORDER
        )
        return [name for name in preferred_order if name in self._providers]

    async def _run_single_provider(
        self, provider_name: str, query: str, max_results: int
    ) -> ProviderOutcome:
        provider = self._providers[provider_name]
        try:
            response = await provider.search(query, max_results=max_results)
            return ProviderOutcome(provider=provider_name, succeeded=True, response=response)
        except SearchProviderError as exc:
            return ProviderOutcome(
                provider=provider_name, succeeded=False, error_message=exc.message
            )
        except Exception as exc:  # noqa: BLE001 — any unexpected provider
            # failure must degrade gracefully rather than crash the router.
            return ProviderOutcome(
                provider=provider_name, succeeded=False, error_message=str(exc)
            )

    async def route(self, analysis: QueryAnalysis) -> RoutedSearchResult:
        """
        Executes the search across all configured (or, for time-sensitive
        queries, preference-ordered) providers concurrently. Returns a
        RoutedSearchResult even if some providers fail, as long as at
        least one succeeds. Raises AllSearchProvidersFailedError only if
        every attempted provider fails.
        """
        if analysis.intent == QueryIntent.CONVERSATIONAL or not analysis.requires_search:
            return RoutedSearchResult(query=analysis.original_query, responses=[], outcomes=[])

        provider_order = self._resolve_provider_order(analysis)
        if not provider_order:
            raise AllSearchProvidersFailedError(attempted_providers=[])

        max_results = self._resolve_result_count(analysis)

        tasks = [
            self._run_single_provider(provider_name, analysis.original_query, max_results)
            for provider_name in provider_order
        ]
        outcomes = await asyncio.gather(*tasks)

        successful_responses = [
            outcome.response for outcome in outcomes if outcome.succeeded and outcome.response
        ]

        if not successful_responses:
            raise AllSearchProvidersFailedError(attempted_providers=list(provider_order))

        return RoutedSearchResult(
            query=analysis.original_query,
            responses=successful_responses,
            outcomes=list(outcomes),
        )