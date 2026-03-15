---
phase: 2
plan: 4
wave: 2
depends_on: []
files_modified:
  - app/infrastructure/cache/redis_cache.py
  - app/infrastructure/cache/rate_limiter.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Redis cache adapter supports get/set/delete with TTL and serialization"
    - "Redis rate limiter implements sliding window algorithm"
    - "Both use async redis client (redis.asyncio)"
    - "Connection uses settings from RedisSettings"
---

# Plan 2.4: Redis Cache & Rate Limiter

## Objective
Implement Redis-based caching (for embeddings and search results) and rate limiting (sliding window). These are critical for production: caching reduces OpenAI API costs, rate limiting protects the service.

## Context
- @app/core/config/settings.py — RedisSettings (host, port, db, password, url property)
- @app/core/config/settings.py — RateLimitSettings (requests_per_minute, burst_size)
- @app/domain/value_objects/embedding.py — EmbeddingVector (for caching)

## Tasks

<task type="auto">
  <name>Implement Redis cache adapter</name>
  <files>app/infrastructure/cache/redis_cache.py</files>
  <action>
    Implement `RedisCache`:
    
    Constructor:
    - Takes `url: str` (from RedisSettings.url property)
    - Creates `redis.asyncio.from_url(url)` lazily
    
    Methods:
    1. `async def get(self, key: str) -> bytes | None`:
       - Get raw bytes from Redis
    
    2. `async def set(self, key: str, value: bytes, ttl_seconds: int = 3600) -> None`:
       - Set with expiration
    
    3. `async def delete(self, key: str) -> bool`:
       - Delete key, return True if existed
    
    4. `async def get_json(self, key: str) -> dict | None`:
       - Get + JSON deserialize
    
    5. `async def set_json(self, key: str, value: dict, ttl_seconds: int = 3600) -> None`:
       - JSON serialize + set
    
    6. `async def close(self) -> None`:
       - Close the connection pool
    
    Helper methods for embedding cache:
    7. `def _embedding_key(self, text: str, model: str) -> str`:
       - Create deterministic cache key: `embed:{model}:{sha256(text)[:16]}`
    
    8. `async def get_embedding(self, text: str, model: str) -> EmbeddingVector | None`:
       - Look up cached embedding
    
    9. `async def set_embedding(self, text: str, model: str, embedding: EmbeddingVector, ttl: int = 86400) -> None`:
       - Cache an embedding (24h TTL default)
    
    Use structlog for cache hit/miss logging.
  </action>
  <verify>python -m poetry run python -c "from app.infrastructure.cache.redis_cache import RedisCache; print('OK')"</verify>
  <done>RedisCache with get/set/delete + embedding-specific cache methods</done>
</task>

<task type="auto">
  <name>Implement Redis rate limiter</name>
  <files>app/infrastructure/cache/rate_limiter.py</files>
  <action>
    Implement `RedisRateLimiter`:
    
    Constructor:
    - Takes `redis_cache: RedisCache`, `requests_per_minute: int`, `burst_size: int`
    
    Methods:
    1. `async def is_allowed(self, key: str) -> bool`:
       - Sliding window rate limiting using Redis sorted sets
       - Key format: `rate:{key}`
       - Algorithm:
         a. Remove entries older than 60 seconds
         b. Count remaining entries
         c. If count < requests_per_minute: add current timestamp, return True
         d. Else return False
       - Use Redis pipeline for atomicity
    
    2. `async def get_remaining(self, key: str) -> int`:
       - Return how many requests remain in the current window
    
    3. `async def reset(self, key: str) -> None`:
       - Clear the rate limit for a key
    
    Log rate limit hits/misses with structlog.
  </action>
  <verify>python -m poetry run python -c "from app.infrastructure.cache.rate_limiter import RedisRateLimiter; print('OK')"</verify>
  <done>RedisRateLimiter with sliding window algorithm using Redis sorted sets</done>
</task>

## Success Criteria
- [ ] `RedisCache` supports raw bytes, JSON, and embedding-specific caching
- [ ] `RedisRateLimiter` implements sliding window rate limiting
- [ ] Both use `redis.asyncio` for non-blocking operations
- [ ] Cache keys are deterministic and collision-resistant
