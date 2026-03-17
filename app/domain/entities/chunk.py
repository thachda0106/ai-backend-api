"""Chunk entity representing a document fragment."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.domain.entities.base import Entity
from app.domain.value_objects.embedding import EmbeddingVector
from app.domain.value_objects.identifiers import ChunkId, CollectionId, DocumentId
from app.domain.value_objects.tenant_id import TenantId


class Chunk(Entity):
    """A chunk of text extracted from a document.

    Chunks are the atomic units for embedding and vector search.
    Each chunk knows its position within the source document
    and may optionally have an embedding attached.
    """

    tenant_id: TenantId
    chunk_id: ChunkId = Field(default_factory=ChunkId)
    document_id: DocumentId
    collection_id: CollectionId
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    token_count: int = 0
    embedding: EmbeddingVector | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def set_embedding(self, embedding: EmbeddingVector) -> None:
        """Attach an embedding vector to this chunk.

        Args:
            embedding: The generated embedding vector.
        """
        self.embedding = embedding
        self.update()

    def has_embedding(self) -> bool:
        """Check if this chunk has an embedding attached."""
        return self.embedding is not None
