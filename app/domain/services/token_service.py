"""Abstract token counting service."""

from __future__ import annotations

from abc import ABC, abstractmethod


class TokenService(ABC):
    """Abstract interface for token counting and cost estimation.

    The concrete implementation (using tiktoken) lives in the
    infrastructure layer to keep the domain free of external deps.
    """

    @abstractmethod
    def count_tokens(self, text: str, model: str) -> int:
        """Count the number of tokens in text for a specific model.

        Args:
            text: The text to count tokens for.
            model: The model name (affects tokenization).

        Returns:
            Number of tokens.
        """

    @abstractmethod
    def estimate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
    ) -> float:
        """Estimate the cost in USD for a given token usage.

        Args:
            prompt_tokens: Number of input tokens.
            completion_tokens: Number of output tokens.
            model: The model name (affects pricing).

        Returns:
            Estimated cost in USD.
        """

    @abstractmethod
    def truncate_to_token_limit(
        self,
        text: str,
        max_tokens: int,
        model: str,
    ) -> str:
        """Truncate text to fit within a token limit.

        Args:
            text: The text to truncate.
            max_tokens: Maximum number of tokens allowed.
            model: The model name (affects tokenization).

        Returns:
            Truncated text that fits within the token limit.
        """
