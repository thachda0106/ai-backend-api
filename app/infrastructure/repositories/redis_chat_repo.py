"""Redis-backed chat history repository.

Persists chat history in Redis lists with automatic pruning
to prevent unbounded growth.
"""

from __future__ import annotations

import json

import structlog

from app.domain.entities.chat import ChatMessage, MessageRole
from app.domain.repositories.chat_repository import ChatHistoryRepository
from app.domain.value_objects.identifiers import UserId
from app.infrastructure.cache.redis_cache import RedisCache

logger = structlog.get_logger(__name__)

_MAX_HISTORY_SIZE = 100


class RedisChatHistoryRepository(ChatHistoryRepository):
    """Redis-backed chat history storage.

    Stores messages in Redis lists keyed by user ID.
    Automatically trims history to prevent unbounded growth.
    """

    def __init__(self, redis_cache: RedisCache) -> None:
        self._redis = redis_cache

    def _history_key(self, user_id: UserId) -> str:
        """Generate the Redis key for a user's chat history."""
        return f"chat:{user_id.value}"

    async def save_message(self, user_id: UserId, message: ChatMessage) -> None:
        """Save a chat message to the user's history."""
        key = self._history_key(user_id)
        data = json.dumps({
            "role": message.role.value,
            "content": message.content,
            "metadata": message.metadata,
        }).encode("utf-8")

        client = self._redis.client
        async with client.pipeline(transaction=True) as pipe:
            pipe.rpush(key, data)
            pipe.ltrim(key, -_MAX_HISTORY_SIZE, -1)
            pipe.expire(key, 86400 * 7)  # 7-day TTL
            await pipe.execute()

    async def get_history(
        self, user_id: UserId, limit: int = 10
    ) -> list[ChatMessage]:
        """Retrieve recent chat history for a user."""
        key = self._history_key(user_id)
        client = self._redis.client

        # Get last `limit` messages
        raw_messages: list[bytes] = await client.lrange(key, -limit, -1)

        messages: list[ChatMessage] = []
        for raw in raw_messages:
            try:
                data = json.loads(raw)
                messages.append(
                    ChatMessage(
                        role=MessageRole(data["role"]),
                        content=data["content"],
                        metadata=data.get("metadata", {}),
                    )
                )
            except (json.JSONDecodeError, KeyError, ValueError):
                await logger.awarning(
                    "invalid_chat_history_entry",
                    user_id=str(user_id.value),
                )
                continue

        return messages

    async def clear_history(self, user_id: UserId) -> None:
        """Clear all chat history for a user."""
        key = self._history_key(user_id)
        await self._redis.delete(key)
        await logger.ainfo(
            "chat_history_cleared",
            user_id=str(user_id.value),
        )
