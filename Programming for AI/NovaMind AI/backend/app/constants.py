# backend/app/constants.py

"""
Centralized constants for NovaMind.
No magic strings/numbers should exist outside this file for the values below.
"""

from enum import Enum


# ── Auth & security ──────────────────────────────────────────────────────

ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
REFRESH_TOKEN_EXPIRE_DAYS: int = 30
JWT_ALGORITHM: str = "HS256"
PASSWORD_MIN_LENGTH: int = 8
PASSWORD_MAX_LENGTH: int = 128
BCRYPT_ROUNDS: int = 12

EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

ACCESS_TOKEN_TYPE: str = "access"
REFRESH_TOKEN_TYPE: str = "refresh"
EMAIL_VERIFICATION_TOKEN_TYPE: str = "email_verification"
PASSWORD_RESET_TOKEN_TYPE: str = "password_reset"


# ── Search modes ─────────────────────────────────────────────────────────

class SearchMode(str, Enum):
    NORMAL = "normal"
    RESEARCH = "research"
    DEEP_RESEARCH = "deep_research"
    ACADEMIC = "academic"
    TECHNICAL = "technical"


SEARCH_MODE_SOURCE_COUNT: dict[str, int] = {
    SearchMode.NORMAL.value: 4,
    SearchMode.RESEARCH.value: 7,
    SearchMode.DEEP_RESEARCH.value: 12,
    SearchMode.ACADEMIC.value: 8,
    SearchMode.TECHNICAL.value: 6,
}

SEARCH_MODE_CONTEXT_TOKEN_BUDGET: dict[str, int] = {
    SearchMode.NORMAL.value: 3000,
    SearchMode.RESEARCH.value: 6000,
    SearchMode.DEEP_RESEARCH.value: 12000,
    SearchMode.ACADEMIC.value: 7000,
    SearchMode.TECHNICAL.value: 5000,
}


# ── Search providers ─────────────────────────────────────────────────────

class SearchProviderName(str, Enum):
    TAVILY = "tavily"
    BRAVE = "brave"


SEARCH_PROVIDER_TIMEOUT_SECONDS: float = 5.0
SEARCH_PROVIDER_MAX_RETRIES: int = 1
SEARCH_PROVIDER_HEALTH_WINDOW: int = 20
SEARCH_PROVIDER_HEALTH_MIN_SUCCESS_RATE: float = 0.70
SEARCH_PROVIDER_HEALTH_TTL_SECONDS: int = 300


# ── LLM / NVIDIA ──────────────────────────────────────────────────────────

class NvidiaModel(str, Enum):
    LLAMA_3_3_70B = "meta/llama-3.3-70b-instruct"
    LLAMA_3_1_70B = "meta/llama-3.1-70b-instruct"
    MISTRAL_LARGE = "mistralai/mistral-large"
    DEEPSEEK_R1 = "deepseek-ai/deepseek-r1"
    NV_EMBED_QA = "nvidia/nv-embedqa-e5-v5"


DEFAULT_LLM_MODEL: str = NvidiaModel.LLAMA_3_3_70B.value
DEFAULT_CLASSIFIER_MODEL: str = NvidiaModel.LLAMA_3_1_70B.value
EMBEDDING_MODEL: str = NvidiaModel.NV_EMBED_QA.value
EMBEDDING_DIMENSIONS: int = 1024

NVIDIA_API_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
NVIDIA_REQUEST_TIMEOUT_SECONDS: float = 60.0
NVIDIA_MAX_TOKENS_DEFAULT: int = 2048
NVIDIA_TEMPERATURE_DEFAULT: float = 0.3
NVIDIA_MAX_RETRIES_PER_KEY: int = 2
NVIDIA_RATE_LIMIT_STATUS_CODE: int = 429


class NvidiaKeySlot(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


# ── Task-based model routing ─────────────────────────────────────────────

class TaskType(str, Enum):
    GENERAL = "general"
    REASONING = "reasoning"
    CODE = "code"


TASK_TYPE_MODEL_MAP: dict[str, str] = {
    TaskType.GENERAL.value: NvidiaModel.LLAMA_3_3_70B.value,
    TaskType.REASONING.value: NvidiaModel.DEEPSEEK_R1.value,
    TaskType.CODE.value: NvidiaModel.MISTRAL_LARGE.value,
}


# ── Source ranking ───────────────────────────────────────────────────────

SOURCE_RANK_WEIGHT_AUTHORITY: float = 0.4
SOURCE_RANK_WEIGHT_RELEVANCE: float = 0.4
SOURCE_RANK_WEIGHT_RECENCY: float = 0.2

HIGH_AUTHORITY_TLDS: tuple[str, ...] = (".gov", ".edu", ".org")
HIGH_AUTHORITY_DOMAIN_SCORE: float = 0.9
DEFAULT_DOMAIN_SCORE: float = 0.5


# ── RAG / documents ───────────────────────────────────────────────────────

class DocumentType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    TXT = "txt"


class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


DOCUMENT_CHUNK_SIZE_TOKENS: int = 512
DOCUMENT_CHUNK_OVERLAP_TOKENS: int = 64
DOCUMENT_MAX_FILE_SIZE_MB: int = 25
DOCUMENT_RETRIEVAL_TOP_K: int = 5


# ── Cache ─────────────────────────────────────────────────────────────────

SEARCH_RESULT_CACHE_TTL_SECONDS: int = 300
SESSION_CACHE_TTL_SECONDS: int = 3600
CACHE_KEY_PREFIX_SEARCH: str = "novamind:search:"
CACHE_KEY_PREFIX_SESSION: str = "novamind:session:"
CACHE_KEY_PREFIX_PROVIDER_HEALTH: str = "novamind:provider_health:"
CACHE_KEY_PREFIX_RATE_LIMIT: str = "novamind:rate_limit:"


# ── API / pagination ──────────────────────────────────────────────────────

API_V1_PREFIX: str = "/api/v1"
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100

CONVERSATION_HISTORY_TURNS_IN_CONTEXT: int = 6
FOLLOW_UP_QUESTIONS_COUNT: int = 3


# ── Roles / message types ────────────────────────────────────────────────

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class UserPlan(str, Enum):
    FREE = "free"
    PRO = "pro"


# ── SSE event names ───────────────────────────────────────────────────────

class SSEEvent(str, Enum):
    SOURCES = "sources"
    TOKEN = "token"
    CITATION = "citation"
    DONE = "done"
    ERROR = "error"