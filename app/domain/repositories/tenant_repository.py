"""Abstract tenant repository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.tenant import Tenant
from app.domain.value_objects.tenant_id import TenantId


class TenantRepository(ABC):
    """Abstract interface for tenant persistence.

    Implementations store tenants in PostgreSQL and cache
    API key lookups in Redis for performance.
    """

    @abstractmethod
    async def get_by_id(self, tenant_id: TenantId) -> Tenant | None:
        """Retrieve a tenant by its ID. Returns None if not found."""

    @abstractmethod
    async def get_by_api_key_hash(self, api_key_hash: str) -> Tenant | None:
        """Retrieve a tenant by hashed API key.

        Used in authentication middleware. Implementations should
        cache this lookup (e.g., 5-minute Redis TTL).
        """

    @abstractmethod
    async def save(self, tenant: Tenant) -> Tenant:
        """Persist a new tenant. Returns the saved tenant."""

    @abstractmethod
    async def update(self, tenant: Tenant) -> Tenant:
        """Update an existing tenant. Returns the updated tenant."""

    @abstractmethod
    async def delete(self, tenant_id: TenantId) -> bool:
        """Soft delete a tenant (set is_active=False). Returns True if found."""
