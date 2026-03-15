"""Tiktoken-based token counting service.

Implements the domain TokenService ABC using OpenAI's tiktoken
library for accurate, model-specific token counting.
"""

from __future__ import annotations

import tiktoken

from app.domain.services.token_service import TokenService

# Pricing per 1M tokens (input/output) as of March 2026
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Chat models: (input_per_1M, output_per_1M)
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    # Embedding models: (input_per_1M, 0)
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
    "text-embedding-ada-002": (0.10, 0.0),
}

# Fallback encoding for unknown models
_FALLBACK_ENCODING = "cl100k_base"


class TiktokenService(TokenService):
    """Token counting service using tiktoken.

    Caches encoding instances by model name for performance.
    Falls back to cl100k_base for unknown models.
    """

    def __init__(self) -> None:
        self._encodings: dict[str, tiktoken.Encoding] = {}

    def _get_encoding(self, model: str) -> tiktoken.Encoding:
        """Get or create a cached tiktoken Encoding for the given model."""
        if model not in self._encodings:
            try:
                self._encodings[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Unknown model — fall back to cl100k_base
                self._encodings[model] = tiktoken.get_encoding(_FALLBACK_ENCODING)
        return self._encodings[model]

    def count_tokens(self, text: str, model: str) -> int:
        """Count tokens in text using model-specific encoding.

        Args:
            text: The text to tokenize.
            model: The OpenAI model name (e.g., 'gpt-4o').

        Returns:
            Number of tokens.
        """
        encoding = self._get_encoding(model)
        return len(encoding.encode(text))

    def estimate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
    ) -> float:
        """Estimate API cost in USD based on token usage.

        Args:
            prompt_tokens: Number of input/prompt tokens.
            completion_tokens: Number of output/completion tokens.
            model: The OpenAI model name.

        Returns:
            Estimated cost in USD. Returns 0.0 for unknown models.
        """
        pricing = _MODEL_PRICING.get(model)
        if pricing is None:
            return 0.0

        input_price_per_1m, output_price_per_1m = pricing
        input_cost = (prompt_tokens / 1_000_000) * input_price_per_1m
        output_cost = (completion_tokens / 1_000_000) * output_price_per_1m
        return input_cost + output_cost

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
            model: The OpenAI model name.

        Returns:
            The truncated text. If text is already within limit, returns as-is.
        """
        encoding = self._get_encoding(model)
        tokens = encoding.encode(text)

        if len(tokens) <= max_tokens:
            return text

        truncated_tokens = tokens[:max_tokens]
        return encoding.decode(truncated_tokens)
