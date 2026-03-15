"""Abstract base classes for LLM providers.

These ABCs define the contract for embedding and chat completion
providers. Domain and application layers depend on these abstractions,
not on concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from app.domain.entities.chat import ChatMessage, ChatResponse
from app.domain.value_objects.embedding import EmbeddingVector


class EmbeddingProvider(ABC):
    """Abstract interface for text-to-vector embedding services."""

    @abstractmethod
    async def embed(self, text: str) -> EmbeddingVector:
        """Generate an embedding vector for a single text.

        Args:
            text: The text to embed.

        Returns:
            An EmbeddingVector value object.

        Raises:
            EmbeddingException: If embedding generation fails.
            LLMRateLimitException: If the provider rate limit is hit.
            LLMConnectionException: If the provider is unreachable.
        """

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]:
        """Generate embeddings for multiple texts in a single API call.

        Args:
            texts: List of texts to embed.

        Returns:
            A list of EmbeddingVector value objects, in the same order as inputs.

        Raises:
            EmbeddingException: If embedding generation fails.
            LLMRateLimitException: If the provider rate limit is hit.
        """


class ChatProvider(ABC):
    """Abstract interface for chat completion services."""

    @abstractmethod
    async def complete(self, messages: list[ChatMessage]) -> ChatResponse:
        """Generate a chat completion for the given message history.

        Args:
            messages: Ordered list of chat messages (system, user, assistant).

        Returns:
            A ChatResponse with the assistant's reply and token usage.

        Raises:
            LLMException: If completion fails.
            LLMRateLimitException: If the provider rate limit is hit.
            TokenLimitExceededException: If the prompt exceeds the context window.
        """

    @abstractmethod
    async def stream(self, messages: list[ChatMessage]) -> AsyncGenerator[str, None]:
        """Stream a chat completion, yielding content deltas.

        Args:
            messages: Ordered list of chat messages.

        Yields:
            Content deltas (text fragments) as they are generated.

        Raises:
            LLMException: If streaming fails.
            LLMRateLimitException: If the provider rate limit is hit.
        """
