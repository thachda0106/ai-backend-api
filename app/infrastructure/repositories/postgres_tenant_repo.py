"""PostgreSQL-backed tenant repository with Redis caching.

Tenant lookups by API key are cached in Redis (5-minute TTL)
to avoid repeated DB round-trips on every request.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from app.domain.entities.tenant import Tenant, TenantPlan
from app.domain.repositories.tenant_repository import TenantRepository
from app.domain.value_objects.tenant_id import TenantId
from app.infrastructure.cache.redis_cache import RedisCache
from app.infrastructure.db.postgres_pool import PostgresPool

logger = structlog.get_logger(__name__)

_CACHE_TTL = 300  # 5 minutes
_CACHE_PREFIX = "tenant:key:"


class PostgresTenantRepository(TenantRepository):
    """PostgreSQL tenant repository with Redis cache-aside for API key lookups."""

    def __init__(self, pool: PostgresPool, cache: RedisCache) -> None:
        self._pool = pool
        self._cache = cache

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_tenant(row: Any) -> Tenant:
        return Tenant(
            tenant_id=TenantId(value=row["tenant_id"]),
            name=row["name"],
            api_key_hash=row["api_key_hash"],
            plan=TenantPlan(row["plan"]),
            is_active=row["is_active"],
            tokens_used_this_month=row["tokens_used_this_month"],
            total_tokens_used=row["total_tokens_used"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _cache_key(self, api_key_hash: str) -> str:
        return f"{_CACHE_PREFIX}{api_key_hash}"

    # ── Interface ─────────────────────────────────────────────────────────

    async def get_by_id(self, tenant_id: TenantId) -> Tenant | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM tenants WHERE tenant_id = $1",
            tenant_id.value,
        )
        return self._row_to_tenant(row) if row else None

    async def get_by_api_key_hash(self, api_key_hash: str) -> Tenant | None:
        """Lookup with Redis cache-aside (5-minute TTL)."""
        cache_key = self._cache_key(api_key_hash)

        # 1. Try cache
        cached = await self._cache.get_json(cache_key)
        if cached:
            await logger.adebug("tenant_cache_hit", key_prefix=api_key_hash[:8])
            try:
                return Tenant(**cached)
            except Exception:
                # Corrupt cache entry — fall through to DB
                pass

        # 2. DB lookup
        row = await self._pool.fetchrow(
            "SELECT * FROM tenants WHERE api_key_hash = $1",
            api_key_hash,
        )
        if not row:
            return None

        tenant = self._row_to_tenant(row)

        # 3. Write back to cache
        try:
            tenant_data = tenant.model_dump(mode="json")
            await self._cache.set_json(cache_key, tenant_data, ttl_seconds=_CACHE_TTL)
        except Exception as exc:
            # Cache write failure is non-critical
            await logger.awarning("tenant_cache_write_failed", error=str(exc))

        return tenant

    async def save(self, tenant: Tenant) -> Tenant:
        await self._pool.execute(
            """
            INSERT INTO tenants (
                tenant_id, name, api_key_hash, plan, is_active,
                tokens_used_this_month, total_tokens_used, metadata,
                created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT (tenant_id) DO NOTHING
            """,
            tenant.tenant_id.value,
            tenant.name,
            tenant.api_key_hash,
            tenant.plan.value,
            tenant.is_active,
            tenant.tokens_used_this_month,
            tenant.total_tokens_used,
            json.dumps(tenant.metadata),
            tenant.created_at,
            tenant.updated_at,
        )
        return tenant

    async def update(self, tenant: Tenant) -> Tenant:
        await self._pool.execute(
            """
            UPDATE tenants SET
                is_active = $2, plan = $3,
                tokens_used_this_month = $4, total_tokens_used = $5,
                metadata = $6, updated_at = NOW()
            WHERE tenant_id = $1
            """,
            tenant.tenant_id.value,
            tenant.is_active,
            tenant.plan.value,
            tenant.tokens_used_this_month,
            tenant.total_tokens_used,
            json.dumps(tenant.metadata),
        )
        # Invalidate cached lookup
        cache_key = self._cache_key(tenant.api_key_hash)
        await self._cache.delete(cache_key)
        return tenant

    async def delete(self, tenant_id: TenantId) -> bool:
        result = await self._pool.execute(
            "UPDATE tenants SET is_active = FALSE, updated_at = NOW() WHERE tenant_id = $1",
            tenant_id.value,
        )
        return result == "UPDATE 1"
