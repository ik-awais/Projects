# backend/app/services/providers/tavily.py

"""
Tavily search provider implementation.
"""

import time
from urllib.parse import urlparse

import httpx

from app.constants import SEARCH_PROVIDER_MAX_RETRIES, SEARCH_PROVIDER_TIMEOUT_SECONDS
from app.core.config import settings
from app.exceptions import SearchProviderError
from app.services.providers.base import SearchProvider, SearchResponse, SearchResult

TAVILY_API_URL = "https://api.tavily.com/search"


def _extract_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.replace("www.", "") if netloc else url
    except ValueError:
        return url


class TavilySearchProvider(SearchProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.TAVILY_API_KEY

    @property
    def provider_name(self) -> str:
        return "tavily"

    async def search(self, query: str, *, max_results: int = 5) -> SearchResponse:
        start = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(SEARCH_PROVIDER_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=SEARCH_PROVIDER_TIMEOUT_SECONDS) as client:
                    response = await client.post(
                        TAVILY_API_URL,
                        json={
                            "api_key": self._api_key,
                            "query": query,
                            "max_results": max_results,
                            "search_depth": "basic",
                            "include_answer": False,
                            "include_raw_content": False,
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
                self.provider_name, "Rate limited (HTTP 429) by Tavily API."
            )
        if response.status_code == 401:
            raise SearchProviderError(
                self.provider_name, "Authentication failed — check TAVILY_API_KEY."
            )
        if response.status_code >= 400:
            raise SearchProviderError(
                self.provider_name,
                f"Tavily API returned HTTP {response.status_code}: {response.text[:200]}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SearchProviderError(
                self.provider_name, f"Response was not valid JSON: {exc}"
            ) from exc

        raw_results = payload.get("results")
        if raw_results is None or not isinstance(raw_results, list):
            raise SearchProviderError(
                self.provider_name,
                "Malformed response: expected a 'results' list, got "
                f"{type(raw_results).__name__}.",
            )

        results: list[SearchResult] = []
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            url = raw.get("url")
            title = raw.get("title")
            if not url or not title:
                continue

            results.append(
                SearchResult(
                    title=str(title),
                    url=str(url),
                    domain=_extract_domain(str(url)),
                    snippet=str(raw.get("content") or ""),
                    provider=self.provider_name,
                    score=float(raw.get("score", 0.0)),
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