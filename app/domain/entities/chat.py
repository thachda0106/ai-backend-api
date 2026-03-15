"""Chat-related domain models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.search_result import SearchResult


class MessageRole(str, Enum):
    """Chat message role."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """An individual chat message.

    Frozen (immutable) — messages are never modified after creation.
    """

    model_config = ConfigDict(frozen=True)

    role: MessageRole
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenUsage(BaseModel):
    """Token usage statistics for an LLM request.

    Frozen (immutable) — usage stats are recorded once.
    """

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float = 0.0


class ChatResponse(BaseModel):
    """Complete response from the RAG chat pipeline.

    Includes the assistant message, source citations,
    and token usage statistics.
    """

    message: ChatMessage
    sources: list[SearchResult] = Field(default_factory=list)
    token_usage: TokenUsage | None = None
