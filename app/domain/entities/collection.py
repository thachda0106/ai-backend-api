"""Collection entity for grouping documents."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.domain.entities.base import Entity
from app.domain.value_objects.identifiers import CollectionId


class Collection(Entity):
    """A named collection of documents.

    Collections serve as namespaces for organizing documents
    and their associated vector embeddings.
    """

    collection_id: CollectionId = Field(default_factory=CollectionId)
    name: str
    description: str = ""
    document_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def increment_document_count(self) -> None:
        """Increment the document count by one."""
        self.document_count += 1
        self.update()

    def decrement_document_count(self) -> None:
        """Decrement the document count by one (minimum 0)."""
        self.document_count = max(0, self.document_count - 1)
        self.update()
