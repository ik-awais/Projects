"""
LLM provider abstraction layer.

Defines the provider-independent contract every LLM provider (NVIDIA NIM
and any future provider) must implement: completion, streaming completion,
and embeddings. No provider-specific logic belongs in this file.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum


class LLMMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """A single message in a chat-style completion request."""

    role: LLMMessageRole
    content: str


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """Token usage accounting for a single completion or embedding call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class LLMCompletionResponse:
    """
    The complete, provider-independent result of a non-streaming
    completion call.
    """

    provider: str
    model: str
    content: str
    usage: LLMUsage
    finish_reason: str
    latency_ms: int


@dataclass(frozen=True, slots=True)
class LLMStreamChunk:
    """
    A single incremental chunk emitted during a streaming completion call.
    is_final marks the last chunk, at which point usage and finish_reason
    are populated (providers typically only know final token usage once
    the stream completes).
    """

    provider: str
    model: str
    delta: str
    is_final: bool = False
    finish_reason: str | None = None
    usage: LLMUsage | None = None


@dataclass(frozen=True, slots=True)
class LLMEmbeddingResponse:
    """
    The complete, provider-independent result of an embedding call.
    embeddings is ordered identically to the input texts list passed
    to embed().
    """

    provider: str
    model: str
    embeddings: list[list[float]] = field(default_factory=list)
    usage: LLMUsage = field(default_factory=LLMUsage)
    dimensions: int = 0


class LLMProvider(ABC):
    """
    Abstract base class every concrete LLM provider must subclass.
    Covers three capabilities: completion, streaming completion, and
    embeddings. Routing, prompt assembly, and business logic are
    explicitly out of scope here.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Stable, lowercase identifier for this provider, e.g. 'nvidia'."""
        raise NotImplementedError

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMCompletionResponse:
        """
        Executes a non-streaming chat completion and returns a single,
        fully-formed LLMCompletionResponse.

        Implementations must never raise raw HTTP/library exceptions to
        the caller; failures must be wrapped in app.exceptions.LLMError
        subclasses.
        """
        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        Executes a streaming chat completion and returns an async
        iterator of LLMStreamChunk. The final chunk yielded must have
        is_final=True with finish_reason and usage populated.

        Implementations must never raise raw HTTP/library exceptions
        from within the iterator; failures must be wrapped in
        app.exceptions.LLMError subclasses.
        """
        raise NotImplementedError

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        *,
        model: str,
    ) -> LLMEmbeddingResponse:
        """
        Executes an embedding call for one or more input texts and
        returns a single LLMEmbeddingResponse whose embeddings list is
        ordered identically to the input texts list.

        Implementations must never raise raw HTTP/library exceptions to
        the caller; failures must be wrapped in app.exceptions.LLMError
        subclasses.
        """
        raise NotImplementedError