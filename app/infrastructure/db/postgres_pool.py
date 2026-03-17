"""PostgreSQL connection pool — thin lifecycle wrapper around asyncpg."""

from __future__ import annotations

import asyncpg
import structlog

from app.core.config.settings import DatabaseSettings

logger = structlog.get_logger(__name__)


class PostgresPool:
    """Manages the asyncpg connection pool lifecycle.

    Created once at startup, closed at shutdown.
    All repositories receive a reference to this pool.
    """

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        self._pool: asyncpg.Pool | None = None  # type: ignore[type-arg]

    @property
    def pool(self) -> asyncpg.Pool:  # type: ignore[type-arg]
        """Access the active connection pool."""
        if self._pool is None:
            msg = "PostgresPool not connected. Call connect() first."
            raise RuntimeError(msg)
        return self._pool

    async def connect(self) -> None:
        """Create and warm up the connection pool."""
        self._pool = await asyncpg.create_pool(
            dsn=self._settings.url,
            min_size=self._settings.pool_min_size,
            max_size=self._settings.pool_max_size,
            command_timeout=30,
        )
        await logger.ainfo(
            "postgres_pool_connected",
            host=self._settings.host,
            db=self._settings.db_name,
            min_size=self._settings.pool_min_size,
            max_size=self._settings.pool_max_size,
        )

    async def close(self) -> None:
        """Drain and close all connections in the pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            await logger.ainfo("postgres_pool_closed")

    async def execute(self, query: str, *args: object) -> str:
        """Execute a write query."""
        return await self.pool.execute(query, *args)  # type: ignore[arg-type]

    async def fetch(self, query: str, *args: object) -> list[asyncpg.Record]:
        """Execute a read query returning multiple rows."""
        return await self.pool.fetch(query, *args)  # type: ignore[arg-type]

    async def fetchrow(self, query: str, *args: object) -> asyncpg.Record | None:
        """Execute a read query returning a single row."""
        return await self.pool.fetchrow(query, *args)  # type: ignore[arg-type]

    async def fetchval(self, query: str, *args: object) -> object:
        """Execute a query returning a single scalar value."""
        return await self.pool.fetchval(query, *args)  # type: ignore[arg-type]
