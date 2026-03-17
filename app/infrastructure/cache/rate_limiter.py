"""Redis-based rate limiter — TOCTOU fix with Lua script (IMP-7) + public property (CRIT-8).

The original implementation had a race condition:
  pipeline(zremrangebyscore, zcard, zadd) → zadd already done → zrem if over limit
  Between the pipeline and the zrem, another request could read stale count.

Fix: atomic Lua script does the entire check-and-update in one Redis call.
"""

from __future__ import annotations

import time

import structlog

from app.infrastructure.cache.redis_cache import RedisCache

logger = structlog.get_logger(__name__)

# Atomic Lua script: remove expired, check count, conditionally add entry
# Returns 1 if allowed, 0 if rate limited
_RATE_LIMIT_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- Remove entries outside the window
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)

-- Count current requests in window
local count = redis.call('ZCARD', key)

if count < limit then
    -- Add this request (score = timestamp for ordered eviction)
    -- Use now+math.random() to avoid duplicate score collisions
    redis.call('ZADD', key, now, now .. ':' .. math.random(1000000))
    redis.call('EXPIRE', key, math.ceil(window))
    return 1
end

return 0
"""


class RedisRateLimiter:
    """Sliding window rate limiter backed by Redis sorted sets.

    Uses an atomic Lua script for all check-and-update operations,
    eliminating the TOCTOU race condition in the original pipeline approach.
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
        self._script: object = None  # Cached registered Lua script

    @property
    def limit(self) -> int:
        """Public accessor for the configured rate limit. (CRIT-8 Fix)"""
        return self._requests_per_minute

    def _rate_key(self, key: str) -> str:
        return f"rate:{key}"

    async def _get_script(self) -> object:
        """Register the Lua script once and cache the returned object."""
        if self._script is None:
            self._script = self._redis.client.register_script(_RATE_LIMIT_LUA)
        return self._script

    async def is_allowed(self, key: str) -> bool:
        """Check if a request is allowed under the rate limit.

        Uses an atomic Lua script — genuinely TOCTOU-free (IMP-7 Fix):
        1. Remove expired entries (> 60s old)
        2. Count remaining entries
        3. If under limit, add current timestamp and return 1 (allowed)
        4. Else return 0 (denied) — nothing written to Redis

        Args:
            key: The rate limit key (e.g., API key or IP address).

        Returns:
            True if the request is allowed, False if rate limited.
        """
        rate_key = self._rate_key(key)
        now = time.time()
        window_seconds = 60.0

        try:
            script = await self._get_script()
            result = await script(  # type: ignore[operator]
                keys=[rate_key],
                args=[now, window_seconds, self._requests_per_minute],
            )
            allowed = bool(result)
        except Exception as exc:
            # Redis failure: fail open (allow request, don't break service)
            await logger.awarning(
                "rate_limiter_lua_error",
                key=key,
                error=str(exc),
            )
            return True

        if not allowed:
            await logger.awarning(
                "rate_limit_exceeded",
                key=key,
                limit=self._requests_per_minute,
            )

        return allowed

    async def get_remaining(self, key: str) -> int:
        """Return how many requests remain in the current window."""
        rate_key = self._rate_key(key)
        now = time.time()
        window_start = now - 60.0

        try:
            client = self._redis.client
            await client.zremrangebyscore(rate_key, "-inf", window_start)
            current_count: int = await client.zcard(rate_key)
            return max(0, self._requests_per_minute - current_count)
        except Exception:
            return self._requests_per_minute  # fail open

    async def reset(self, key: str) -> None:
        """Clear the rate limit for a key."""
        rate_key = self._rate_key(key)
        await self._redis.delete(rate_key)
        await logger.ainfo("rate_limit_reset", key=key)
