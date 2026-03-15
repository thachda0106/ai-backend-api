"""Qdrant vector store adapter.

Implements the VectorRepository ABC using Qdrant's AsyncQdrantClient
for non-blocking vector storage and similarity search.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config.settings import QdrantSettings
from app.domain.entities.search_result import SearchResult
from app.domain.value_objects.embedding import EmbeddingVector
from app.domain.value_objects.identifiers import ChunkId, DocumentId
from app.domain.repositories.vector_repository import VectorRepository

logger = structlog.get_logger(__name__)


class QdrantVectorRepository(VectorRepository):
    """Qdrant-backed vector repository.

    Uses AsyncQdrantClient with gRPC transport for optimal performance.
    All operations are non-blocking.
    """

    def __init__(self, settings: QdrantSettings) -> None:
        self._settings = settings
        self._client: AsyncQdrantClient | None = None

    @property
    def client(self) -> AsyncQdrantClient:
        """Lazily create the async Qdrant client."""
        if self._client is None:
            self._client = AsyncQdrantClient(
                host=self._settings.host,
                port=self._settings.port,
                grpc_port=self._settings.grpc_port,
                prefer_grpc=self._settings.prefer_grpc,
            )
        return self._client

    @property
    def collection_name(self) -> str:
        """Get the configured collection name."""
        return self._settings.collection_name

    async def upsert(
        self,
        chunk_id: ChunkId,
        embedding: EmbeddingVector,
        metadata: dict[str, Any],
    ) -> None:
        """Insert or update a single vector."""
        await self.upsert_many([(chunk_id, embedding, metadata)])

    async def upsert_many(
        self,
        entries: list[tuple[ChunkId, EmbeddingVector, dict[str, Any]]],
    ) -> None:
        """Insert or update multiple vectors in a batch."""
        if not entries:
            return

        start_time = time.monotonic()

        points = [
            PointStruct(
                id=str(chunk_id.value),
                vector=list(embedding.values),
                payload=metadata,
            )
            for chunk_id, embedding, metadata in entries
        ]

        await self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

        elapsed = time.monotonic() - start_time
        await logger.ainfo(
            "qdrant_upsert",
            collection=self.collection_name,
            point_count=len(points),
            elapsed_seconds=round(elapsed, 3),
        )

    async def search(
        self,
        query_embedding: EmbeddingVector,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform similarity search and return ranked results."""
        start_time = time.monotonic()

        query_filter = _build_filter(filters) if filters else None

        results = await self.client.query_points(
            collection_name=self.collection_name,
            query=list(query_embedding.values),
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        elapsed = time.monotonic() - start_time

        search_results = [
            SearchResult(
                chunk_id=ChunkId.from_str(str(point.id)),
                score=point.score,
                content=point.payload.get("content", "") if point.payload else "",
                metadata=point.payload if point.payload else {},
            )
            for point in results.points
        ]

        await logger.ainfo(
            "qdrant_search",
            collection=self.collection_name,
            top_k=top_k,
            results_count=len(search_results),
            has_filters=filters is not None,
            elapsed_seconds=round(elapsed, 3),
        )

        return search_results

    async def delete(self, chunk_id: ChunkId) -> bool:
        """Delete a single vector by chunk ID."""
        result = await self.client.delete(
            collection_name=self.collection_name,
            points_selector=[str(chunk_id.value)],
        )

        await logger.ainfo(
            "qdrant_delete",
            collection=self.collection_name,
            chunk_id=str(chunk_id.value),
        )
        return result is not None

    async def delete_by_document(self, document_id: DocumentId) -> int:
        """Delete all vectors for a document using payload filter."""
        start_time = time.monotonic()

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=str(document_id.value)),
                        )
                    ]
                )
            ),
        )

        elapsed = time.monotonic() - start_time
        await logger.ainfo(
            "qdrant_delete_by_document",
            collection=self.collection_name,
            document_id=str(document_id.value),
            elapsed_seconds=round(elapsed, 3),
        )

        # Qdrant doesn't return deletion count for filter-based deletes
        return 0

    async def ensure_collection(
        self,
        collection_name: str,
        vector_size: int,
    ) -> None:
        """Ensure collection exists with correct vector configuration."""
        exists = await self.client.collection_exists(collection_name)

        if not exists:
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            await logger.ainfo(
                "qdrant_collection_created",
                collection=collection_name,
                vector_size=vector_size,
                distance="cosine",
            )
        else:
            await logger.ainfo(
                "qdrant_collection_exists",
                collection=collection_name,
            )

    async def close(self) -> None:
        """Close the Qdrant client connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            await logger.ainfo("qdrant_client_closed")


def _build_filter(filters: dict[str, Any]) -> Filter:
    """Build a Qdrant Filter from a simple dict of field conditions."""
    conditions = [
        FieldCondition(key=key, match=MatchValue(value=value))
        for key, value in filters.items()
    ]
    return Filter(must=conditions)
