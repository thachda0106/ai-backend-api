"""Search result domain data class."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.value_objects.identifiers import ChunkId, CollectionId, DocumentId


class SearchResult(BaseModel):
    """An individual search result from vector similarity search.

    This is a frozen (immutable) data class, not an entity.
    It represents the output of a search query.
    """

    model_config = ConfigDict(frozen=True)

    chunk_id: ChunkId
    document_id: DocumentId
    collection_id: CollectionId
    content: str
    score: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    document_title: str = ""
    chunk_index: int = 0
