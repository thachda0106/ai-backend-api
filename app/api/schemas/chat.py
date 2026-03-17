"""Chat API request/response schemas.

These are the HTTP contract schemas — separate from application DTOs.
Includes both standard JSON response and SSE streaming event schemas.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Request body for RAG chat."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "What are the best practices for error handling?",
                    "stream": True,
                    "top_k": 5,
                }
            ]
        }
    )

    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,  # CRIT-7: prevent unbounded token burn
        description="User message / question to answer using RAG",
    )
    conversation_id: str | None = Field(
        default=None,
        description="Conversation ID for multi-turn chat continuity",
    )
    user_id: str | None = Field(
        default=None,
        description="User ID for chat history tracking",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of context chunks to retrieve (1-20)",
    )
    stream: bool = Field(
        default=False,
        description="If true, response is streamed via Server-Sent Events (SSE)",
    )


class SourceResponse(BaseModel):
    """A cited source in the chat response."""

    index: int = Field(..., description="Citation index (1-based)")
    chunk_id: str = Field(..., description="Source chunk identifier")
    document_id: str = Field(..., description="Source document identifier")
    document_title: str = Field(default="", description="Title of the source document")
    content: str = Field(default="", description="Preview of the cited content (truncated)")
    score: float = Field(default=0.0, description="Relevance score of this source")


class ChatResponse(BaseModel):
    """Non-streaming chat response (JSON)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "Based on the documentation, error handling should...",
                    "sources": [
                        {
                            "index": 1,
                            "chunk_id": "c1a2b3c4-d5e6-7890-abcd-ef1234567890",
                            "document_id": "d1e2f3a4-b5c6-7890-abcd-ef1234567890",
                            "document_title": "Error Handling Guide",
                            "content": "Use try/except blocks with specific...",
                            "score": 0.95,
                        }
                    ],
                    "prompt_tokens": 1200,
                    "completion_tokens": 350,
                    "total_tokens": 1550,
                }
            ]
        }
    )

    message: str = Field(..., description="Assistant's response message")
    sources: list[SourceResponse] = Field(
        default_factory=list,
        description="Cited sources used to generate the response",
    )
    prompt_tokens: int = Field(default=0, description="Tokens used in the prompt")
    completion_tokens: int = Field(default=0, description="Tokens in the completion")
    total_tokens: int = Field(default=0, description="Total tokens consumed")


class StreamEvent(BaseModel):
    """SSE streaming event payload (sent as data: {json})."""

    content: str = Field(default="", description="Content delta for this chunk")
    done: bool = Field(default=False, description="True for the final event in the stream")
    sources: list[SourceResponse] | None = Field(
        default=None,
        description="Cited sources (only present in the final event)",
    )
    prompt_tokens: int | None = Field(
        default=None,
        description="Prompt tokens (only present in the final event)",
    )
    completion_tokens: int | None = Field(
        default=None,
        description="Completion tokens (only present in the final event)",
    )
    total_tokens: int | None = Field(
        default=None,
        description="Total tokens (only present in the final event)",
    )
