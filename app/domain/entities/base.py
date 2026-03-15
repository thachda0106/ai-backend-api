"""Base entity class with identity and timestamps."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class Entity(BaseModel):
    """Base class for all domain entities.

    Entities have identity (id), timestamps, and are mutable.
    Equality is based on the id field (entity identity pattern).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def update(self) -> None:
        """Update the updated_at timestamp to the current time."""
        self.updated_at = datetime.now(UTC)

    def __eq__(self, other: object) -> bool:
        """Entity equality is based on identity (id field)."""
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on entity id for use in sets and as dict keys."""
        return hash(self.id)
