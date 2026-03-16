"""Search API request/response schemas.

These are the HTTP contract schemas — separate from application DTOs.
Routers map between these schemas and application DTOs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    """Request body for semantic document search."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "How do I configure the database connection?",
                    "top_k": 5,
                    "collection_id": None,
                    "filters": None,
                }
            ]
        }
    )

    query: str = Field(
        ...,
        min_length=1,
        description="Natural language search query",
    )
    collection_id: str | None = Field(
        default=None,
        description="Filter results to a specific document collection",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)",
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata filters for narrowing results",
    )


class SearchResultResponse(BaseModel):
    """A single search result in the response."""

    chunk_id: str = Field(..., description="Unique identifier for the matched chunk")
    document_id: str = Field(..., description="Parent document identifier")
    content: str = Field(..., description="Text content of the matched chunk")
    score: float = Field(..., description="Similarity score (0.0-1.0, higher is better)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    document_title: str = Field(default="", description="Title of the parent document")
    chunk_index: int = Field(default=0, description="Position of this chunk within the document")


class SearchResponse(BaseModel):
    """Response containing ranked search results."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "results": [
                        {
                            "chunk_id": "c1a2b3c4-d5e6-7890-abcd-ef1234567890",
                            "document_id": "d1e2f3a4-b5c6-7890-abcd-ef1234567890",
                            "content": "To configure the database, set the DATABASE_URL...",
                            "score": 0.92,
                            "metadata": {},
                            "document_title": "Getting Started Guide",
                            "chunk_index": 3,
                        }
                    ],
                    "total": 1,
                    "query_tokens": 8,
                }
            ]
        }
    )

    results: list[SearchResultResponse] = Field(
        default_factory=list,
        description="Ranked search results ordered by relevance score",
    )
    total: int = Field(default=0, description="Total number of results returned")
    query_tokens: int = Field(default=0, description="Number of tokens in the query")
