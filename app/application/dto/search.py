"""Search-related Data Transfer Objects."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Input DTO for semantic search."""

    query: str = Field(..., min_length=1)
    collection_id: str | None = None
    top_k: int = Field(default=10, ge=1, le=100)
    filters: dict[str, Any] | None = None


class SearchResultDTO(BaseModel):
    """Output DTO for a single search result."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    document_title: str = ""
    chunk_index: int = 0


class SearchResponse(BaseModel):
    """Output DTO for search results."""

    results: list[SearchResultDTO] = Field(default_factory=list)
    total: int = 0
    query_tokens: int = 0
