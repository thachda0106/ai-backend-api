"""Redis cache adapter.

Provides async Redis caching with support for raw bytes,
JSON, and embedding-specific operations.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from app.domain.value_objects.embedding import EmbeddingVector

logger = structlog.get_logger(__name__)


class RedisCache:
    """Async Redis cache adapter.

    Supports raw bytes, JSON serialization, and embedding-specific
    caching with deterministic key generation.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._client: aioredis.Redis | None = None  # type: ignore[type-arg]

    @property
    def client(self) -> aioredis.Redis:  # type: ignore[type-arg]
        """Lazily create the async Redis client."""
        if self._client is None:
            self._client = aioredis.from_url(
                self._url,
                decode_responses=False,
            )
        return self._client

    # ──────────────────────────────────────────────
    # Raw bytes operations
    # ──────────────────────────────────────────────

    async def get(self, key: str) -> bytes | None:
        """Get raw bytes from Redis."""
        value: bytes | None = await self.client.get(key)
        return value

    async def set(self, key: str, value: bytes, ttl_seconds: int = 3600) -> None:
        """Set raw bytes with TTL."""
        await self.client.set(key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> bool:
        """Delete a key. Returns True if key existed."""
        result: int = await self.client.delete(key)
        return result > 0

    # ──────────────────────────────────────────────
    # JSON operations
    # ──────────────────────────────────────────────

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Get and deserialize JSON from Redis."""
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            result: dict[str, Any] = json.loads(raw)
            return result
        except (json.JSONDecodeError, TypeError):
            return None

    async def set_json(
        self, key: str, value: dict[str, Any], ttl_seconds: int = 3600
    ) -> None:
        """Serialize and set JSON in Redis."""
        raw = json.dumps(value).encode("utf-8")
        await self.set(key, raw, ttl_seconds)

    # ──────────────────────────────────────────────
    # Embedding-specific operations
    # ──────────────────────────────────────────────

    @staticmethod
    def _embedding_key(text: str, model: str) -> str:
        """Create a deterministic cache key for an embedding."""
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return f"embed:{model}:{text_hash}"

    async def get_embedding(self, text: str, model: str) -> EmbeddingVector | None:
        """Look up a cached embedding."""
        key = self._embedding_key(text, model)
        data = await self.get_json(key)
        if data is None:
            await logger.adebug("embedding_cache_miss", model=model)
            return None

        await logger.adebug("embedding_cache_hit", model=model)
        return EmbeddingVector(
            values=tuple(data["values"]),
            model=data["model"],
            dimensions=data["dimensions"],
        )

    async def set_embedding(
        self,
        text: str,
        model: str,
        embedding: EmbeddingVector,
        ttl: int = 86400,
    ) -> None:
        """Cache an embedding (default 24h TTL)."""
        key = self._embedding_key(text, model)
        data = {
            "values": list(embedding.values),
            "model": embedding.model,
            "dimensions": embedding.dimensions,
        }
        await self.set_json(key, data, ttl_seconds=ttl)

    # ──────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────

    async def close(self) -> None:
        """Close the Redis connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            await logger.ainfo("redis_cache_closed")
