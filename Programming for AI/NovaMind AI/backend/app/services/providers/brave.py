# backend/app/services/providers/brave.py

"""
Brave search provider implementation.
"""

import time
from urllib.parse import urlparse

import httpx

from app.constants import SEARCH_PROVIDER_MAX_RETRIES, SEARCH_PROVIDER_TIMEOUT_SECONDS
from app.core.config import settings
from app.exceptions import SearchProviderError
from app.services.providers.base import SearchProvider, SearchResponse, SearchResult

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"


def _extract_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.replace("www.", "") if netloc else url
    except ValueError:
        return url


class BraveSearchProvider(SearchProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.BRAVE_API_KEY

    @property
    def provider_name(self) -> str:
        return "brave"

    async def search(self, query: str, *, max_results: int = 5) -> SearchResponse:
        start = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(SEARCH_PROVIDER_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=SEARCH_PROVIDER_TIMEOUT_SECONDS) as client:
                    response = await client.get(
                        BRAVE_API_URL,
                        params={
                            "q": query,
                            "count": max_results,
                        },
                        headers={
                            "Accept": "application/json",
                            "X-Subscription-Token": self._api_key,
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
                self.provider_name, "Rate limited (HTTP 429) by Brave Search API."
            )
        if response.status_code == 401 or response.status_code == 403:
            raise SearchProviderError(
                self.provider_name, "Authentication failed — check BRAVE_API_KEY."
            )
        if response.status_code >= 400:
            raise SearchProviderError(
                self.provider_name,
                f"Brave API returned HTTP {response.status_code}: {response.text[:200]}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SearchProviderError(
                self.provider_name, f"Response was not valid JSON: {exc}"
            ) from exc

        web_section = payload.get("web")
        if web_section is None or not isinstance(web_section, dict):
            raise SearchProviderError(
                self.provider_name,
                "Malformed response: expected a 'web' object, got "
                f"{type(web_section).__name__}.",
            )

        raw_results = web_section.get("results")
        if raw_results is None or not isinstance(raw_results, list):
            raise SearchProviderError(
                self.provider_name,
                "Malformed response: expected 'web.results' to be a list, got "
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

            # Brave does not return a numeric relevance score in its
            # response payload. A deterministic, rank-derived score is
            # synthesized here (highest for the first result, decreasing
            # linearly) so the field is always populated with a real
            # float, consistent with Tavily's score field, rather than
            # leaving it as a fabricated constant.
            position_score = max(0.0, 1.0 - (index * (1.0 / max(len(raw_results), 1))))

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