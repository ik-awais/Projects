# backend/app/services/providers/firecrawl.py

"""
Firecrawl search provider implementation.

Uses Firecrawl's /v2/search endpoint to return web search results.
Without scrapeOptions, each result costs 2 credits per 10 results
(the free tier provides 1,000 credits/month — approximately 5,000
searches/month at this usage rate). The scrapeOptions parameter is
intentionally not used here: this provider's responsibility is search
result retrieval only, keeping the per-call cost at the base rate.
Full-page content extraction for RAG (Sprint 3) will use Firecrawl's
/v2/scrape endpoint via a separate service, not this provider.
"""

import time
from urllib.parse import urlparse

import httpx

from app.constants import SEARCH_PROVIDER_MAX_RETRIES, SEARCH_PROVIDER_TIMEOUT_SECONDS
from app.core.config import settings
from app.exceptions import SearchProviderError
from app.services.providers.base import SearchProvider, SearchResponse, SearchResult

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v2/search"


def _extract_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.replace("www.", "") if netloc else url
    except ValueError:
        return url


class FirecrawlSearchProvider(SearchProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.FIRECRAWL_API_KEY

    @property
    def provider_name(self) -> str:
        return "firecrawl"

    async def search(self, query: str, *, max_results: int = 5) -> SearchResponse:
        start = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(SEARCH_PROVIDER_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=SEARCH_PROVIDER_TIMEOUT_SECONDS
                ) as client:
                    response = await client.post(
                        FIRECRAWL_API_URL,
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "query": query,
                            "limit": max_results,
                            "sources": ["web"],
                        },
                    )
                return self._handle_response(response, query, start)

            except httpx.TimeoutException as exc:
                last_error = exc
                continue
            except httpx.RequestError as exc:
                last_error = exc
                continue

        raise SearchProviderError(
            self.provider_name,
            f"Request failed after {SEARCH_PROVIDER_MAX_RETRIES + 1} attempt(s): {last_error}",
        )

    def _handle_response(
        self, response: httpx.Response, query: str, start_time: float
    ) -> SearchResponse:
        if response.status_code == 429:
            raise SearchProviderError(
                self.provider_name, "Rate limited (HTTP 429) by Firecrawl API."
            )
        if response.status_code == 401 or response.status_code == 403:
            raise SearchProviderError(
                self.provider_name, "Authentication failed — check FIRECRAWL_API_KEY."
            )
        if response.status_code >= 400:
            raise SearchProviderError(
                self.provider_name,
                f"Firecrawl API returned HTTP {response.status_code}: {response.text[:200]}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SearchProviderError(
                self.provider_name, f"Response was not valid JSON: {exc}"
            ) from exc

        if not payload.get("success", False):
            raise SearchProviderError(
                self.provider_name,
                f"Firecrawl API returned success=false: {payload.get('error', 'unknown error')}",
            )
 
        data_obj = payload.get("data")
        if data_obj is None or not isinstance(data_obj, dict):
            raise SearchProviderError(
                self.provider_name,
                "Malformed response: expected a 'data' object, got "
                f"{type(data_obj).__name__}.",
            )
        raw_results = data_obj.get("web")
        if raw_results is None or not isinstance(raw_results, list):
            raise SearchProviderError(
                self.provider_name,
                "Malformed response: expected 'data.web' to be a list, got "
                f"{type(raw_results).__name__}.",
            )

        results: list[SearchResult] = []
        for index, raw in enumerate(raw_results):
            if not isinstance(raw, dict):
                continue
            url = raw.get("url")
            title = raw.get("title")
            if not url or not title:
                continue

            # Firecrawl returns an explicit "position" field (1-based rank).
            # Convert to a 0.0-1.0 descending score: position 1 → 1.0,
            # position 2 → lower, etc. Falls back to index if field absent.
            position = int(raw.get("position", index + 1))
            position_score = max(
                0.0, 1.0 - ((position - 1) * (1.0 / max(len(raw_results), 1)))
            )

            results.append(
                SearchResult(
                    title=str(title),
                    url=str(url),
                    domain=_extract_domain(str(url)),
                    snippet=str(raw.get("description") or ""),
                    provider=self.provider_name,
                    score=round(position_score, 4),
                )
            )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        return SearchResponse(
            provider=self.provider_name,
            query=query,
            results=results,
            total_results=len(results),
            search_time_ms=elapsed_ms,
        )