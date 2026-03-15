"""Chat-related Data Transfer Objects."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Input DTO for RAG chat."""

    message: str = Field(..., min_length=1)
    conversation_id: str | None = None
    user_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class SourceDTO(BaseModel):
    """Output DTO for a cited source."""

    index: int
    chunk_id: str
    document_id: str
    document_title: str = ""
    content: str = ""
    score: float = 0.0


class ChatResponseDTO(BaseModel):
    """Output DTO for chat response."""

    message: str
    sources: list[SourceDTO] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class StreamChunk(BaseModel):
    """Output DTO for a streaming chunk."""

    content: str = ""
    done: bool = False
    sources: list[SourceDTO] | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
