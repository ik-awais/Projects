"""
NVIDIA NIM LLM provider implementation.

Supports text generation, streaming generation, and embeddings against
NVIDIA's OpenAI-compatible NIM API, with automatic primary-to-secondary
API key failover on rate limiting or authentication failure.
"""

import json
import time
from collections.abc import AsyncIterator

import httpx

from app.constants import (
    NVIDIA_API_BASE_URL,
    NVIDIA_MAX_RETRIES_PER_KEY,
    NVIDIA_RATE_LIMIT_STATUS_CODE,
    NVIDIA_REQUEST_TIMEOUT_SECONDS,
    NvidiaKeySlot,
)
from app.core.config import settings
from app.exceptions import (
    AllLLMKeysExhaustedError,
    LLMProviderRateLimitedError,
    LLMResponseParsingError,
)
from app.services.llm.base import (
    LLMCompletionResponse,
    LLMEmbeddingResponse,
    LLMMessage,
    LLMProvider,
    LLMStreamChunk,
    LLMUsage,
)

NVIDIA_CHAT_COMPLETIONS_PATH = "/chat/completions"
NVIDIA_EMBEDDINGS_PATH = "/embeddings"


class NvidiaLLMProvider(LLMProvider):
    def __init__(
        self,
        primary_api_key: str | None = None,
        secondary_api_key: str | None = None,
    ) -> None:
        self._primary_api_key = primary_api_key or settings.NVIDIA_API_KEY_1
        self._secondary_api_key = secondary_api_key or settings.NVIDIA_API_KEY_2

    @property
    def provider_name(self) -> str:
        return "nvidia"

    def _keys_in_order(self) -> list[tuple[str, str]]:
        return [
            (NvidiaKeySlot.PRIMARY.value, self._primary_api_key),
            (NvidiaKeySlot.SECONDARY.value, self._secondary_api_key),
        ]

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_chat_payload(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        max_tokens: int,
        temperature: float,
        stream: bool,
    ) -> dict:
        payload = {
            "model": model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in messages
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMCompletionResponse:
        start = time.monotonic()
        payload = self._build_chat_payload(
            messages, model=model, max_tokens=max_tokens, temperature=temperature, stream=False
        )

        last_key_slot_tried: str | None = None

        for key_slot, api_key in self._keys_in_order():
            last_key_slot_tried = key_slot
            for attempt in range(NVIDIA_MAX_RETRIES_PER_KEY):
                try:
                    async with httpx.AsyncClient(
                        base_url=NVIDIA_API_BASE_URL,
                        timeout=NVIDIA_REQUEST_TIMEOUT_SECONDS,
                    ) as client:
                        response = await client.post(
                            NVIDIA_CHAT_COMPLETIONS_PATH,
                            headers=self._headers(api_key),
                            json=payload,
                        )

                    if response.status_code == NVIDIA_RATE_LIMIT_STATUS_CODE:
                        raise LLMProviderRateLimitedError(self.provider_name, key_slot)

                    if response.status_code in (401, 403):
                        raise LLMProviderRateLimitedError(self.provider_name, key_slot)

                    if response.status_code >= 400:
                        raise LLMResponseParsingError(
                            f"NVIDIA API returned HTTP {response.status_code}: "
                            f"{response.text[:200]}"
                        )

                    return self._parse_completion_response(response, model, start)

                except LLMProviderRateLimitedError:
                    break
                except httpx.TimeoutException:
                    if attempt == NVIDIA_MAX_RETRIES_PER_KEY - 1:
                        break
                    continue
                except httpx.RequestError:
                    if attempt == NVIDIA_MAX_RETRIES_PER_KEY - 1:
                        break
                    continue

        raise AllLLMKeysExhaustedError(self.provider_name)

    def _parse_completion_response(
        self, response: httpx.Response, model: str, start_time: float
    ) -> LLMCompletionResponse:
        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMResponseParsingError(f"Response was not valid JSON: {exc}") from exc

        choices = payload.get("choices")
        if not choices or not isinstance(choices, list):
            raise LLMResponseParsingError(
                "Malformed response: expected a non-empty 'choices' list."
            )

        first_choice = choices[0]
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise LLMResponseParsingError(
                "Malformed response: expected 'choices[0].message' to be an object."
            )

        content = message.get("content")
        if content is None:
            raise LLMResponseParsingError(
                "Malformed response: 'choices[0].message.content' is missing."
            )

        usage_raw = payload.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
            completion_tokens=int(usage_raw.get("completion_tokens", 0)),
            total_tokens=int(usage_raw.get("total_tokens", 0)),
        )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        return LLMCompletionResponse(
            provider=self.provider_name,
            model=model,
            content=str(content),
            usage=usage,
            finish_reason=str(first_choice.get("finish_reason") or "unknown"),
            latency_ms=elapsed_ms,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> AsyncIterator[LLMStreamChunk]:
        payload = self._build_chat_payload(
            messages, model=model, max_tokens=max_tokens, temperature=temperature, stream=True
        )

        for key_slot, api_key in self._keys_in_order():
            try:
                async for chunk in self._stream_with_key(
                    payload, model=model, api_key=api_key, key_slot=key_slot
                ):
                    yield chunk
                return
            except LLMProviderRateLimitedError:
                continue
            except httpx.TimeoutException:
                continue
            except httpx.RequestError:
                continue

        raise AllLLMKeysExhaustedError(self.provider_name)

    async def _stream_with_key(
        self,
        payload: dict,
        *,
        model: str,
        api_key: str,
        key_slot: str,
    ) -> AsyncIterator[LLMStreamChunk]:
        accumulated_prompt_tokens = 0
        accumulated_completion_tokens = 0
        accumulated_total_tokens = 0
        pending_finish_reason: str | None = None

        async with httpx.AsyncClient(
            base_url=NVIDIA_API_BASE_URL,
            timeout=NVIDIA_REQUEST_TIMEOUT_SECONDS,
        ) as client:
            async with client.stream(
                "POST",
                NVIDIA_CHAT_COMPLETIONS_PATH,
                headers=self._headers(api_key),
                json=payload,
            ) as response:
                if response.status_code == NVIDIA_RATE_LIMIT_STATUS_CODE:
                    raise LLMProviderRateLimitedError(self.provider_name, key_slot)
                if response.status_code in (401, 403):
                    raise LLMProviderRateLimitedError(self.provider_name, key_slot)
                if response.status_code >= 400:
                    body = await response.aread()
                    raise LLMResponseParsingError(
                        f"NVIDIA API returned HTTP {response.status_code}: "
                        f"{body[:200].decode('utf-8', errors='replace')}"
                    )

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue

                    raw_data = line[len("data:"):].strip()
                    if raw_data == "[DONE]":
                        yield LLMStreamChunk(
                            provider=self.provider_name,
                            model=model,
                            delta="",
                            is_final=True,
                            finish_reason=pending_finish_reason or "stop",
                            usage=LLMUsage(
                                prompt_tokens=accumulated_prompt_tokens,
                                completion_tokens=accumulated_completion_tokens,
                                total_tokens=accumulated_total_tokens,
                            ),
                        )
                        return

                    try:
                        event = json.loads(raw_data)
                    except json.JSONDecodeError as exc:
                        raise LLMResponseParsingError(
                            f"Stream chunk was not valid JSON: {exc}"
                        ) from exc

                    # NVIDIA sends a trailing event carrying only usage,
                    # with an empty choices list. Capture it and continue
                    # waiting for [DONE] rather than indexing into an
                    # empty choices array.
                    usage_raw = event.get("usage")
                    if usage_raw:
                        accumulated_prompt_tokens = int(usage_raw.get("prompt_tokens", 0))
                        accumulated_completion_tokens = int(
                            usage_raw.get("completion_tokens", 0)
                        )
                        accumulated_total_tokens = int(usage_raw.get("total_tokens", 0))

                    choices = event.get("choices")
                    if not choices or not isinstance(choices, list):
                        continue

                    delta_obj = choices[0].get("delta") or {}
                    delta_text = delta_obj.get("content") or ""
                    finish_reason = choices[0].get("finish_reason")

                    if finish_reason:
                        # Remember that the model finished, but do not
                        # yield the final chunk yet — NVIDIA's usage data
                        # arrives in a later event. Keep consuming until
                        # usage arrives or the stream ends with [DONE].
                        pending_finish_reason = str(finish_reason)
                        continue

                    if delta_text:
                        yield LLMStreamChunk(
                            provider=self.provider_name,
                            model=model,
                            delta=delta_text,
                            is_final=False,
                        )

    async def embed(
        self,
        texts: list[str],
        *,
        model: str,
    ) -> LLMEmbeddingResponse:
        payload = {
            "model": model,
            "input": texts,
            "input_type": "query",
        }

        for key_slot, api_key in self._keys_in_order():
            for attempt in range(NVIDIA_MAX_RETRIES_PER_KEY):
                try:
                    async with httpx.AsyncClient(
                        base_url=NVIDIA_API_BASE_URL,
                        timeout=NVIDIA_REQUEST_TIMEOUT_SECONDS,
                    ) as client:
                        response = await client.post(
                            NVIDIA_EMBEDDINGS_PATH,
                            headers=self._headers(api_key),
                            json=payload,
                        )

                    if response.status_code == NVIDIA_RATE_LIMIT_STATUS_CODE:
                        raise LLMProviderRateLimitedError(self.provider_name, key_slot)

                    if response.status_code in (401, 403):
                        raise LLMProviderRateLimitedError(self.provider_name, key_slot)

                    if response.status_code >= 400:
                        raise LLMResponseParsingError(
                            f"NVIDIA API returned HTTP {response.status_code}: "
                            f"{response.text[:200]}"
                        )

                    return self._parse_embedding_response(response, model)

                except LLMProviderRateLimitedError:
                    break
                except httpx.TimeoutException:
                    if attempt == NVIDIA_MAX_RETRIES_PER_KEY - 1:
                        break
                    continue
                except httpx.RequestError:
                    if attempt == NVIDIA_MAX_RETRIES_PER_KEY - 1:
                        break
                    continue

        raise AllLLMKeysExhaustedError(self.provider_name)

    def _parse_embedding_response(
        self, response: httpx.Response, model: str
    ) -> LLMEmbeddingResponse:
        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMResponseParsingError(f"Response was not valid JSON: {exc}") from exc

        data = payload.get("data")
        if not data or not isinstance(data, list):
            raise LLMResponseParsingError(
                "Malformed response: expected a non-empty 'data' list."
            )

        sorted_data = sorted(data, key=lambda item: item.get("index", 0))
        embeddings: list[list[float]] = []
        for item in sorted_data:
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                raise LLMResponseParsingError(
                    "Malformed response: expected each data item to have an "
                    "'embedding' list."
                )
            embeddings.append([float(value) for value in embedding])

        usage_raw = payload.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
            completion_tokens=0,
            total_tokens=int(usage_raw.get("total_tokens", 0)),
        )

        dimensions = len(embeddings[0]) if embeddings else 0

        return LLMEmbeddingResponse(
            provider=self.provider_name,
            model=model,
            embeddings=embeddings,
            usage=usage,
            dimensions=dimensions,
        )