"""Document API request/response schemas.

These are the HTTP contract schemas — separate from application DTOs.
Routers map between these schemas and application DTOs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IngestDocumentRequest(BaseModel):
    """Request body for document ingestion."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Getting Started Guide",
                    "content": "This guide covers the basics of using our RAG platform...",
                    "content_type": "text/plain",
                    "metadata": {"author": "docs-team", "version": "1.0"},
                }
            ]
        }
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Document title for identification and citation",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Full document text content to be chunked and embedded",
    )
    collection_id: str | None = Field(
        default=None,
        description="Optional collection ID to group related documents",
    )
    content_type: str = Field(
        default="text/plain",
        description="MIME type of the document content",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata attached to the document",
    )


class IngestDocumentResponse(BaseModel):
    """Response after successful document ingestion."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "document_id": "d1e2f3a4-b5c6-7890-abcd-ef1234567890",
                    "job_id": "j9a8b7c6-d5e4-3210-fedc-ba0987654321",
                    "status": "processing",
                }
            ]
        }
    )

    document_id: str = Field(..., description="Unique identifier for the ingested document")
    job_id: str = Field(..., description="Background processing job identifier")
    status: str = Field(default="processing", description="Current processing status")
