"""Domain identifier value objects."""

from __future__ import annotations

import uuid
from typing import Self

from pydantic import Field

from app.domain.value_objects.base import ValueObject


class DocumentId(ValueObject):
    """Unique identifier for a document."""

    value: uuid.UUID = Field(default_factory=uuid.uuid4)

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Create a DocumentId from a string UUID."""
        return cls(value=uuid.UUID(value))

    def __str__(self) -> str:
        return str(self.value)


class ChunkId(ValueObject):
    """Unique identifier for a document chunk."""

    value: uuid.UUID = Field(default_factory=uuid.uuid4)

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Create a ChunkId from a string UUID."""
        return cls(value=uuid.UUID(value))

    def __str__(self) -> str:
        return str(self.value)


class CollectionId(ValueObject):
    """Unique identifier for a document collection."""

    value: uuid.UUID = Field(default_factory=uuid.uuid4)

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Create a CollectionId from a string UUID."""
        return cls(value=uuid.UUID(value))

    def __str__(self) -> str:
        return str(self.value)


class UserId(ValueObject):
    """Unique identifier for a user."""

    value: uuid.UUID = Field(default_factory=uuid.uuid4)

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Create a UserId from a string UUID."""
        return cls(value=uuid.UUID(value))

    def __str__(self) -> str:
        return str(self.value)


class IngestionJobId(ValueObject):
    """Unique identifier for an ingestion job."""

    value: uuid.UUID = Field(default_factory=uuid.uuid4)

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Create an IngestionJobId from a string UUID."""
        return cls(value=uuid.UUID(value))

    def __str__(self) -> str:
        return str(self.value)
