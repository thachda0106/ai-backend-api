"""Document-related Data Transfer Objects."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.value_objects.identifiers import CollectionId


class IngestDocumentRequest(BaseModel):
    """Input DTO for document ingestion."""

    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    collection_id: str | None = None
    content_type: str = "text/plain"
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestDocumentResponse(BaseModel):
    """Output DTO for document ingestion."""

    document_id: str
    job_id: str
    status: str = "processing"


class DocumentResponse(BaseModel):
    """Output DTO for document details."""

    document_id: str
    collection_id: str
    title: str
    content_type: str
    status: str
    chunk_count: int = 0
    token_count: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
