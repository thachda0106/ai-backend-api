"""Abstract chat history repository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.chat import ChatMessage
from app.domain.value_objects.identifiers import UserId


class ChatHistoryRepository(ABC):
    """Abstract interface for chat history persistence.

    Stores conversation history per user for context
    in subsequent RAG queries.
    """

    @abstractmethod
    async def save_message(self, user_id: UserId, message: ChatMessage) -> None:
        """Save a chat message to the user's history."""

    @abstractmethod
    async def get_history(self, user_id: UserId, limit: int = 10) -> list[ChatMessage]:
        """Retrieve recent chat history for a user.

        Returns messages in chronological order, limited to the most recent.
        """

    @abstractmethod
    async def clear_history(self, user_id: UserId) -> None:
        """Clear all chat history for a user."""
