"""TenantId value object for multi-tenant isolation."""

from __future__ import annotations

import uuid
from typing import Self

from pydantic import Field

from app.domain.value_objects.base import ValueObject


class TenantId(ValueObject):
    """Unique identifier for a tenant.

    All data in the system is scoped to a tenant.
    Used for row-level isolation in PostgreSQL and
    payload filtering in Qdrant.
    """

    value: uuid.UUID = Field(default_factory=uuid.uuid4)

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Create a TenantId from a string UUID."""
        return cls(value=uuid.UUID(value))

    def __str__(self) -> str:
        return str(self.value)
