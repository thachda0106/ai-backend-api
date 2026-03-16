"""OpenAI chat completion service implementation.

Uses the OpenAI AsyncOpenAI client for chat completions,
supporting both synchronous responses and streaming via SSE.
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Any

import openai
import structlog
from openai import AsyncOpenAI

from app.core.config.settings import OpenAISettings
from app.domain.entities.chat import ChatMessage, ChatResponse, MessageRole, TokenUsage
from app.domain.exceptions.llm import (
    LLMConnectionException,
    LLMException,
    LLMRateLimitException,
    TokenLimitExceededException,
)
from app.infrastructure.llm.base import ChatProvider

logger = structlog.get_logger(__name__)


class OpenAIChatService(ChatProvider):
    """OpenAI-backed chat completion provider.

    Supports both non-streaming and streaming completions.
    Uses AsyncOpenAI with built-in retry logic.
    """

    def __init__(self, settings: OpenAISettings) -> None:
        self._settings = settings
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        """Lazily create the async OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._settings.api_key.get_secret_value(),
                max_retries=self._settings.max_retries,
            )
        return self._client

    async def complete(self, messages: list[ChatMessage]) -> ChatResponse:
        """Generate a chat completion (non-streaming)."""
        model = self._settings.model
        start_time = time.monotonic()

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=_to_openai_messages(messages),
                temperature=self._settings.temperature,
                max_tokens=self._settings.max_tokens,
            )
        except openai.RateLimitError as exc:
            await logger.awarning("openai_chat_rate_limit", model=model)
            raise LLMRateLimitException(
                provider="openai",
                retry_after=_extract_retry_after(exc),
            ) from exc
        except openai.APIConnectionError as exc:
            await logger.aerror("openai_chat_connection_error", model=model, error=str(exc))
            raise LLMConnectionException(
                detail=str(exc),
            ) from exc
        except openai.BadRequestError as exc:
            # Check for context window / token limit errors
            if "maximum context length" in str(exc).lower() or "max_tokens" in str(exc).lower():
                raise TokenLimitExceededException(
                    token_count=0,
                    max_tokens=self._settings.max_tokens,
                ) from exc
            raise LLMException(message=f"OpenAI chat failed: {exc}") from exc
        except openai.OpenAIError as exc:
            await logger.aerror(
                "openai_chat_error",
                model=model,
                status_code=getattr(exc, "status_code", None),
                error=str(exc),
            )
            raise LLMException(message=f"OpenAI chat failed: {exc}") from exc

        elapsed = time.monotonic() - start_time
        choice = response.choices[0]
        usage = response.usage

        token_usage = TokenUsage(
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )

        assistant_message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=choice.message.content or "",
        )

        await logger.ainfo(
            "openai_chat_complete",
            model=model,
            prompt_tokens=token_usage.prompt_tokens,
            completion_tokens=token_usage.completion_tokens,
            total_tokens=token_usage.total_tokens,
            elapsed_seconds=round(elapsed, 3),
        )

        return ChatResponse(
            message=assistant_message,
            token_usage=token_usage,
        )

    async def stream(self, messages: list[ChatMessage]) -> AsyncGenerator[str, None]:
        """Stream a chat completion, yielding content deltas."""
        model = self._settings.model
        start_time = time.monotonic()

        try:
            response_stream = await self.client.chat.completions.create(
                model=model,
                messages=_to_openai_messages(messages),
                temperature=self._settings.temperature,
                max_tokens=self._settings.max_tokens,
                stream=True,
            )
        except openai.RateLimitError as exc:
            await logger.awarning("openai_stream_rate_limit", model=model)
            raise LLMRateLimitException(
                provider="openai",
                retry_after=_extract_retry_after(exc),
            ) from exc
        except openai.APIConnectionError as exc:
            await logger.aerror("openai_stream_connection_error", model=model, error=str(exc))
            raise LLMConnectionException(
                detail=str(exc),
            ) from exc
        except openai.OpenAIError as exc:
            await logger.aerror("openai_stream_error", model=model, error=str(exc))
            raise LLMException(message=f"OpenAI stream failed: {exc}") from exc

        token_count = 0
        try:
            async for chunk in response_stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        token_count += 1
                        yield delta.content
        except openai.OpenAIError as exc:
            await logger.aerror("openai_stream_interrupted", model=model, error=str(exc))
            raise LLMException(message=f"OpenAI stream interrupted: {exc}") from exc

        elapsed = time.monotonic() - start_time
        await logger.ainfo(
            "openai_stream_complete",
            model=model,
            chunks_yielded=token_count,
            elapsed_seconds=round(elapsed, 3),
        )


def _to_openai_messages(messages: list[ChatMessage]) -> list[dict[str, str]]:
    """Convert domain ChatMessage objects to OpenAI message format."""
    return [{"role": msg.role.value, "content": msg.content} for msg in messages]


def _extract_retry_after(exc: openai.RateLimitError) -> float | None:
    """Extract retry-after seconds from rate limit error headers."""
    response: Any = getattr(exc, "response", None)
    if response is not None:
        retry_after = response.headers.get("retry-after")
        if retry_after is not None:
            try:
                return float(retry_after)
            except (ValueError, TypeError):
                pass
    return None
