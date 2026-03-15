"""User entity for token usage tracking."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.domain.entities.base import Entity
from app.domain.value_objects.identifiers import UserId


class User(Entity):
    """A user of the AI Backend API.

    Tracks cumulative token usage and request counts
    for billing and rate limiting purposes.
    """

    user_id: UserId = Field(default_factory=UserId)
    name: str
    email: str | None = None
    total_tokens_used: int = 0
    total_requests: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def track_usage(self, tokens: int) -> None:
        """Record token usage for this user.

        Args:
            tokens: Number of tokens consumed in a request.
        """
        self.total_tokens_used += tokens
        self.total_requests += 1
        self.update()
