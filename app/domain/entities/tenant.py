"""Tenant entity — top-level multi-tenant boundary."""

from __future__ import annotations

import hashlib
import secrets
from enum import Enum
from typing import Any

from pydantic import Field

from app.domain.entities.base import Entity
from app.domain.value_objects.tenant_id import TenantId


class TenantPlan(str, Enum):
    """Subscription plan tiers."""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# Token quotas per plan (per month)
_PLAN_QUOTAS: dict[TenantPlan, int] = {
    TenantPlan.FREE: 100_000,
    TenantPlan.STARTER: 1_000_000,
    TenantPlan.PRO: 10_000_000,
    TenantPlan.ENTERPRISE: 1_000_000_000,  # effectively unlimited
}


class Tenant(Entity):
    """A tenant of the AI Backend API.

    Each tenant has isolated data (documents, chunks, chat history)
    and its own API key, token quota, and rate limits.
    """

    tenant_id: TenantId = Field(default_factory=TenantId)
    name: str
    api_key_hash: str  # SHA256 hash of the raw API key — never store plaintext
    plan: TenantPlan = TenantPlan.FREE
    is_active: bool = True
    tokens_used_this_month: int = 0
    total_tokens_used: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def generate_api_key() -> str:
        """Generate a cryptographically secure API key.

        Returns the plaintext key — store it once; only the hash is persisted.
        Format: sk-<32 random hex bytes>
        """
        return f"sk-{secrets.token_hex(32)}"

    @staticmethod
    def hash_api_key(raw_key: str) -> str:
        """Hash an API key for safe storage (SHA-256)."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @classmethod
    def create(cls, name: str, plan: TenantPlan = TenantPlan.FREE) -> tuple["Tenant", str]:
        """Create a new tenant and return (Tenant, raw_api_key).

        The raw_api_key is returned exactly once — store it safely.
        """
        raw_key = cls.generate_api_key()
        key_hash = cls.hash_api_key(raw_key)
        tenant = cls(name=name, api_key_hash=key_hash, plan=plan)
        return tenant, raw_key

    @property
    def token_quota(self) -> int:
        """Monthly token quota for this tenant's plan."""
        return _PLAN_QUOTAS[self.plan]

    def can_accept_request(self) -> bool:
        """Check if this tenant can make requests (active + within quota)."""
        return self.is_active and self.tokens_used_this_month < self.token_quota

    def deduct_quota(self, tokens: int) -> None:
        """Record token usage against this tenant's monthly quota."""
        self.tokens_used_this_month += tokens
        self.total_tokens_used += tokens
        self.update()

    def reset_monthly_quota(self) -> None:
        """Reset monthly token counter (called by a monthly cron job)."""
        self.tokens_used_this_month = 0
        self.update()

    def verify_api_key(self, raw_key: str) -> bool:
        """Verify a raw API key against the stored hash."""
        return self.api_key_hash == self.hash_api_key(raw_key)

    def deactivate(self) -> None:
        """Disable this tenant (blocks all requests)."""
        self.is_active = False
        self.update()
