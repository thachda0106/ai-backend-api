"""OpenAI embedding service — with Redis cache-aside (CRIT-4 Fix).

Uses the OpenAI AsyncOpenAI client for text embeddings.
All calls check Redis cache first to avoid redundant API calls.
Cache hit rate target: >80% for repeated queries.
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
    """OpenAI-backed embedding provider with Redis caching.

    Cache strategy:
    - Single embed: check cache → miss → OpenAI → cache write
    - Batch embed: separate cached/uncached → call OpenAI for uncached only
      → write uncached results back to cache
    """

    def __init__(
        self,
        settings: OpenAISettings,
        cache: Any | None = None,  # RedisCache | None — avoid circular import
    ) -> None:
        self._settings = settings
        self._cache = cache
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
        """Generate an embedding for a single text (cache-aware)."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]:
        """Generate embeddings for multiple texts.

        Checks Redis cache per-text before calling OpenAI.
        Only uncached texts are sent to the API; results are written back.
        """
        if not texts:
            return []

        model = self._settings.embedding_model

        # ── 1. Separate cached vs uncached ────────────────────────────
        results: list[EmbeddingVector | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []
        cache_hits = 0

        if self._cache is not None:
            for i, text in enumerate(texts):
                cached = await self._cache.get_embedding(text, model)
                if cached is not None:
                    results[i] = cached
                    cache_hits += 1
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(text)
        else:
            uncached_indices = list(range(len(texts)))
            uncached_texts = list(texts)

        await logger.adebug(
            "embedding_cache_stats",
            total=len(texts),
            cache_hits=cache_hits,
            api_calls_needed=len(uncached_texts),
        )

        # ── 2. Call OpenAI only for uncached texts ────────────────────
        if uncached_texts:
            fresh_embeddings = await self._call_openai(uncached_texts, model)

            # ── 3. Write uncached results back to cache ───────────────
            for idx, (original_idx, text, embedding) in enumerate(
                zip(uncached_indices, uncached_texts, fresh_embeddings)
            ):
                results[original_idx] = embedding
                if self._cache is not None:
                    try:
                        await self._cache.set_embedding(text, model, embedding)
                    except Exception as cache_exc:
                        # Cache write failure is non-critical
                        await logger.awarning(
                            "embedding_cache_write_failed", error=str(cache_exc)
                        )

        return results  # type: ignore[return-value]

    async def _call_openai(
        self, texts: list[str], model: str
    ) -> list[EmbeddingVector]:
        """Make the actual OpenAI embeddings API call."""
        dimensions = self._settings.embedding_dimensions
        start_time = time.monotonic()

        try:
            response = await self.client.embeddings.create(
                model=model,
                input=texts,
            )
        except openai.RateLimitError as exc:
            await logger.awarning("openai_rate_limit", model=model, text_count=len(texts))
            raise LLMRateLimitException(
                provider="openai",
                retry_after=_extract_retry_after(exc),
            ) from exc
        except openai.APIConnectionError as exc:
            await logger.aerror("openai_connection_error", model=model, error=str(exc))
            raise LLMConnectionException(detail=str(exc)) from exc
        except openai.OpenAIError as exc:
            await logger.aerror(
                "openai_embedding_error",
                model=model,
                status_code=getattr(exc, "status_code", None),
                error=str(exc),
            )
            raise EmbeddingException(detail=str(exc)) from exc

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
