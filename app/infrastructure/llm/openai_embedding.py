"""OpenAI embedding service implementation.

Uses the OpenAI AsyncOpenAI client to generate text embeddings.
Supports single and batch embedding with built-in retry logic.
"""

from __future__ import annotations

import time
from typing import Any

import openai
import structlog
from openai import AsyncOpenAI

from app.core.config.settings import OpenAISettings
from app.domain.exceptions.llm import (
    EmbeddingException,
    LLMConnectionException,
    LLMRateLimitException,
)
from app.domain.value_objects.embedding import EmbeddingVector
from app.infrastructure.llm.base import EmbeddingProvider

logger = structlog.get_logger(__name__)


class OpenAIEmbeddingService(EmbeddingProvider):
    """OpenAI-backed embedding provider.

    Uses AsyncOpenAI with built-in retry logic (max_retries from settings).
    Maps OpenAI exceptions to domain exceptions.
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

    async def embed(self, text: str) -> EmbeddingVector:
        """Generate an embedding for a single text."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]:
        """Generate embeddings for multiple texts in a single API call."""
        if not texts:
            return []

        model = self._settings.embedding_model
        dimensions = self._settings.embedding_dimensions
        start_time = time.monotonic()

        try:
            response = await self.client.embeddings.create(
                model=model,
                input=texts,
            )
        except openai.RateLimitError as exc:
            await logger.awarning(
                "openai_rate_limit",
                model=model,
                text_count=len(texts),
            )
            raise LLMRateLimitException(
                provider="openai",
                retry_after=_extract_retry_after(exc),
            ) from exc
        except openai.APIConnectionError as exc:
            await logger.aerror(
                "openai_connection_error",
                model=model,
                error=str(exc),
            )
            raise LLMConnectionException(
                detail=str(exc),
            ) from exc
        except openai.OpenAIError as exc:
            await logger.aerror(
                "openai_embedding_error",
                model=model,
                status_code=getattr(exc, "status_code", None),
                error=str(exc),
            )
            raise EmbeddingException(
                detail=str(exc),
            ) from exc

        elapsed = time.monotonic() - start_time
        usage = response.usage

        await logger.ainfo(
            "openai_embedding_complete",
            model=model,
            text_count=len(texts),
            dimensions=dimensions,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            elapsed_seconds=round(elapsed, 3),
        )

        return [
            EmbeddingVector(
                values=tuple(item.embedding),
                model=model,
                dimensions=dimensions,
            )
            for item in response.data
        ]


def _extract_retry_after(exc: openai.RateLimitError) -> float | None:
    """Extract retry-after seconds from rate limit error headers."""
    response = getattr(exc, "response", None)
    if response is not None:
        retry_after: Any = response.headers.get("retry-after")
        if retry_after is not None:
            try:
                return float(retry_after)
            except (ValueError, TypeError):
                pass
    return None
