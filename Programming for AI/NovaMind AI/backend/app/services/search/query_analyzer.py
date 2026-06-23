"""
Query analysis layer.

Pure, provider-independent analysis of an incoming user query: determines
search intent, estimates appropriate search depth, and produces a
structured QueryAnalysis object consumed by search_router.py. Contains
no provider-specific logic and makes no external calls (no LLM, no HTTP)
so it remains fast, deterministic, and independently testable.
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from app.constants import SearchMode


class QueryIntent(str, Enum):
    FACTUAL = "factual"
    NEWS = "news"
    RESEARCH = "research"
    COMPARISON = "comparison"
    CONVERSATIONAL = "conversational"


_NEWS_PATTERNS = (
    r"\btoday\b", r"\byesterday\b", r"\bthis week\b", r"\bbreaking\b",
    r"\blatest\b", r"\brecent(ly)?\b", r"\bcurrent(ly)?\b", r"\bnow\b",
    r"\bjust (announced|released|happened)\b", r"\bnews\b", r"\bupdate(s)?\b",
)

_COMPARISON_PATTERNS = (
    r"\bvs\.?\b", r"\bversus\b", r"\bcompared? to\b", r"\bcompare\b",
    r"\bdifference between\b", r"\bbetter than\b", r"\bwhich (is|one)\b",
    r"\bor\b.*\?",
)

_RESEARCH_PATTERNS = (
    r"\bwhy\b", r"\bhow does\b", r"\bhow do\b", r"\bexplain\b",
    r"\banalysis\b", r"\bin depth\b", r"\bcomprehensive\b",
    r"\bpros and cons\b", r"\bimplications?\b", r"\bdeep dive\b",
    r"\bresearch\b", r"\bstudy\b", r"\bhistory of\b",
)

_CONVERSATIONAL_PATTERNS = (
    r"^(hi|hello|hey|thanks|thank you|ok|okay|sure|got it)\b",
    r"\bwhat do you think\b", r"\bcan you help\b", r"\bi need help\b",
    r"^(yes|no|maybe)\b",
)

_FACTUAL_PATTERNS = (
    r"^(what|who|when|where) is\b", r"^(what|who|when|where) are\b",
    r"\bdefine\b", r"\bdefinition of\b", r"\bmeaning of\b",
    r"\bhow many\b", r"\bhow much\b", r"\bcapital of\b",
)

_COMPILED_PATTERNS: dict[QueryIntent, list[re.Pattern[str]]] = {
    QueryIntent.NEWS: [re.compile(p, re.IGNORECASE) for p in _NEWS_PATTERNS],
    QueryIntent.COMPARISON: [re.compile(p, re.IGNORECASE) for p in _COMPARISON_PATTERNS],
    QueryIntent.RESEARCH: [re.compile(p, re.IGNORECASE) for p in _RESEARCH_PATTERNS],
    QueryIntent.CONVERSATIONAL: [re.compile(p, re.IGNORECASE) for p in _CONVERSATIONAL_PATTERNS],
    QueryIntent.FACTUAL: [re.compile(p, re.IGNORECASE) for p in _FACTUAL_PATTERNS],
}

# Evaluated in this priority order when multiple intents match — earlier
# entries win, since e.g. a news+factual hybrid query should route as NEWS
# (time-sensitive providers) rather than FACTUAL (static answer).
_INTENT_PRIORITY: tuple[QueryIntent, ...] = (
    QueryIntent.CONVERSATIONAL,
    QueryIntent.NEWS,
    QueryIntent.COMPARISON,
    QueryIntent.RESEARCH,
    QueryIntent.FACTUAL,
)

_INTENT_TO_SEARCH_MODE: dict[QueryIntent, str] = {
    QueryIntent.CONVERSATIONAL: SearchMode.NORMAL.value,
    QueryIntent.FACTUAL: SearchMode.NORMAL.value,
    QueryIntent.NEWS: SearchMode.NORMAL.value,
    QueryIntent.COMPARISON: SearchMode.RESEARCH.value,
    QueryIntent.RESEARCH: SearchMode.RESEARCH.value,
}

_MIN_QUERY_LENGTH_FOR_SEARCH = 2
_LONG_QUERY_WORD_THRESHOLD = 12


@dataclass(frozen=True, slots=True)
class QueryAnalysis:
    """
    Structured, provider-independent analysis of a single user query.
    Consumed by search_router.py to decide which providers to call and
    how many results to request.
    """

    original_query: str
    intent: QueryIntent
    suggested_search_mode: str
    requires_search: bool
    estimated_depth: int
    detected_entities: list[str] = field(default_factory=list)
    is_time_sensitive: bool = False


def _matches_any(query: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(pattern.search(query) for pattern in patterns)


def _classify_intent(query: str) -> QueryIntent:
    for intent in _INTENT_PRIORITY:
        if _matches_any(query, _COMPILED_PATTERNS[intent]):
            return intent
    return QueryIntent.FACTUAL


def _estimate_depth(query: str, intent: QueryIntent) -> int:
    """
    Returns an integer depth signal (1-3) used by search_router.py to
    decide how many results to request per provider. Not a result count
    itself — search_router.py maps this to actual counts via constants.
    """
    word_count = len(query.split())

    if intent == QueryIntent.CONVERSATIONAL:
        return 1
    if intent in (QueryIntent.RESEARCH, QueryIntent.COMPARISON):
        return 3
    if word_count >= _LONG_QUERY_WORD_THRESHOLD:
        return 2
    return 1


def _extract_entities(query: str) -> list[str]:
    """
    Lightweight, dependency-free entity extraction: capitalized
    multi-word sequences (proper-noun heuristic). This is intentionally
    simple — full NER would require an external model, which this pure
    analysis layer does not call.
    """
    capitalized_words = re.findall(r"\b[A-Z][a-zA-Z0-9]*(?:\s[A-Z][a-zA-Z0-9]*)*\b", query)
    seen: set[str] = set()
    entities: list[str] = []
    for candidate in capitalized_words:
        normalized = candidate.strip()
        if not normalized or normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        entities.append(normalized)
    return entities


def _requires_search(query: str, intent: QueryIntent) -> bool:
    stripped = query.strip()
    if len(stripped) < _MIN_QUERY_LENGTH_FOR_SEARCH:
        return False
    if intent == QueryIntent.CONVERSATIONAL:
        return False
    return True


async def analyze_query(query: str) -> QueryAnalysis:
    """
    Analyzes a raw user query and returns a structured QueryAnalysis.
    Async for interface consistency with the rest of the search pipeline,
    though this implementation performs no I/O and completes synchronously.

    Raises ValueError if the query is empty or whitespace-only — callers
    are expected to validate non-empty input before reaching this layer.
    """
    if not query or not query.strip():
        raise ValueError("Query must not be empty or whitespace-only.")

    normalized_query = query.strip()
    intent = _classify_intent(normalized_query)
    depth = _estimate_depth(normalized_query, intent)
    entities = _extract_entities(normalized_query)
    requires_search = _requires_search(normalized_query, intent)
    is_time_sensitive = intent == QueryIntent.NEWS

    return QueryAnalysis(
        original_query=normalized_query,
        intent=intent,
        suggested_search_mode=_INTENT_TO_SEARCH_MODE[intent],
        requires_search=requires_search,
        estimated_depth=depth,
        detected_entities=entities,
        is_time_sensitive=is_time_sensitive,
    )