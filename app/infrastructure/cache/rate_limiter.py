"""Redis-based rate limiter.

Implements sliding window rate limiting using Redis sorted sets
with pipeline for atomic operations.
"""

from __future__ import annotations

import time

import structlog

from app.infrastructure.cache.redis_cache import RedisCache

logger = structlog.get_logger(__name__)


class RedisRateLimiter:
    """Sliding window rate limiter backed by Redis sorted sets.

    Uses Redis pipelines for atomic check-and-update operations.
    Each key tracks timestamps of recent requests in a sorted set.
    """

    def __init__(
        self,
        redis_cache: RedisCache,
        requests_per_minute: int = 60,
        burst_size: int = 10,
    ) -> None:
        self._redis = redis_cache
        self._requests_per_minute = requests_per_minute
        self._burst_size = burst_size

    def _rate_key(self, key: str) -> str:
        """Generate the Redis key for rate limiting."""
        return f"rate:{key}"

    async def is_allowed(self, key: str) -> bool:
        """Check if a request is allowed under the rate limit.

        Uses sliding window algorithm:
        1. Remove expired entries (older than 60s)
        2. Count remaining entries
        3. If under limit, add current timestamp and allow
        4. Otherwise, deny

        Args:
            key: The rate limit key (e.g., API key or IP).

        Returns:
            True if the request is allowed, False if rate limited.
        """
        rate_key = self._rate_key(key)
        now = time.time()
        window_start = now - 60.0

        client = self._redis.client
        async with client.pipeline(transaction=True) as pipe:
            # Remove old entries outside the window
            pipe.zremrangebyscore(rate_key, "-inf", window_start)
            # Count current entries
            pipe.zcard(rate_key)
            # Add current request
            pipe.zadd(rate_key, {str(now): now})
            # Set key expiration
            pipe.expire(rate_key, 60)

            results = await pipe.execute()

        current_count: int = results[1]

        if current_count < self._requests_per_minute:
            return True

        # Over limit — remove the entry we just added
        await client.zrem(rate_key, str(now))

        await logger.awarning(
            "rate_limit_exceeded",
            key=key,
            current_count=current_count,
            limit=self._requests_per_minute,
        )
        return False

    async def get_remaining(self, key: str) -> int:
        """Return how many requests remain in the current window.

        Args:
            key: The rate limit key.

        Returns:
            Number of remaining allowed requests.
        """
        rate_key = self._rate_key(key)
        now = time.time()
        window_start = now - 60.0

        client = self._redis.client
        # Clean up expired entries first
        await client.zremrangebyscore(rate_key, "-inf", window_start)
        current_count: int = await client.zcard(rate_key)

        remaining = max(0, self._requests_per_minute - current_count)
        return remaining

    async def reset(self, key: str) -> None:
        """Clear the rate limit for a key.

        Args:
            key: The rate limit key to reset.
        """
        rate_key = self._rate_key(key)
        await self._redis.delete(rate_key)
        await logger.ainfo("rate_limit_reset", key=key)
