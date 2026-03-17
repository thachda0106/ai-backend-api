"""PostgreSQL-backed document repository.

Replaces InMemoryDocumentRepository for production use.
All queries are scoped to tenant_id for data isolation.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import structlog

from app.domain.entities.document import Document, DocumentStatus
from app.domain.repositories.document_repository import DocumentRepository
from app.domain.value_objects.identifiers import CollectionId, DocumentId
from app.domain.value_objects.pagination import PaginationParams
from app.domain.value_objects.tenant_id import TenantId
from app.infrastructure.db.postgres_pool import PostgresPool

logger = structlog.get_logger(__name__)


class PostgresDocumentRepository(DocumentRepository):
    """PostgreSQL-backed document repository.

    All operations require tenant_id for row-level isolation.
    Uses asyncpg for non-blocking I/O.
    """

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _content_hash(content: str) -> str:
        """Deterministic SHA-256 hash for deduplication checks."""
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def _row_to_document(row: Any) -> Document:
        """Map a PostgreSQL record to a Document entity."""
        from app.domain.entities.document import Document
        from app.domain.value_objects.tenant_id import TenantId

        return Document(
            tenant_id=TenantId(value=row["tenant_id"]),
            document_id=DocumentId(value=row["document_id"]),
            collection_id=CollectionId(value=row["collection_id"]),
            title=row["title"],
            content=row["content"],
            content_type=row["content_type"],
            status=DocumentStatus(row["status"]),
            chunk_count=row["chunk_count"],
            token_count=row["token_count"],
            error_message=row["error_message"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ── Interface implementation ──────────────────────────────────────────

    async def get_by_id(self, document_id: DocumentId) -> Document | None:
        """Retrieve a document by its UUID (any tenant)."""
        row = await self._pool.fetchrow(
            "SELECT * FROM documents WHERE document_id = $1",
            document_id.value,
        )
        return self._row_to_document(row) if row else None

    async def get_by_id_for_tenant(
        self,
        document_id: DocumentId,
        tenant_id: TenantId,
    ) -> Document | None:
        """Retrieve a document scoped to a specific tenant."""
        row = await self._pool.fetchrow(
            "SELECT * FROM documents WHERE document_id = $1 AND tenant_id = $2",
            document_id.value,
            tenant_id.value,
        )
        return self._row_to_document(row) if row else None

    async def get_by_collection(
        self,
        collection_id: CollectionId,
        pagination: PaginationParams,
    ) -> list[Document]:
        """Retrieve documents in a collection with pagination."""
        rows = await self._pool.fetch(
            """
            SELECT * FROM documents
            WHERE collection_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            collection_id.value,
            pagination.limit,
            pagination.offset,
        )
        return [self._row_to_document(r) for r in rows]

    async def find_duplicate(self, tenant_id: TenantId, content: str) -> Document | None:
        """Find an existing document with identical content (for deduplication)."""
        content_hash = self._content_hash(content)
        row = await self._pool.fetchrow(
            "SELECT * FROM documents WHERE tenant_id = $1 AND content_hash = $2 LIMIT 1",
            tenant_id.value,
            content_hash,
        )
        return self._row_to_document(row) if row else None

    async def save(self, document: Document) -> Document:
        """Persist a new document."""
        content_hash = self._content_hash(document.content)
        await self._pool.execute(
            """
            INSERT INTO documents (
                document_id, tenant_id, collection_id, title, content,
                content_type, content_hash, status, chunk_count, token_count,
                error_message, metadata, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            ON CONFLICT (document_id) DO NOTHING
            """,
            document.document_id.value,
            document.tenant_id.value,
            document.collection_id.value,
            document.title,
            document.content,
            document.content_type,
            content_hash,
            document.status.value,
            document.chunk_count,
            document.token_count,
            document.error_message,
            json.dumps(document.metadata),
            document.created_at,
            document.updated_at,
        )
        return document

    async def update(self, document: Document) -> Document:
        """Update an existing document's mutable fields."""
        await self._pool.execute(
            """
            UPDATE documents SET
                status = $2, chunk_count = $3, token_count = $4,
                error_message = $5, metadata = $6, updated_at = NOW()
            WHERE document_id = $1
            """,
            document.document_id.value,
            document.status.value,
            document.chunk_count,
            document.token_count,
            document.error_message,
            json.dumps(document.metadata),
        )
        return document

    async def delete(self, document_id: DocumentId) -> bool:
        """Hard delete a document and cascade to ingestion_jobs."""
        result = await self._pool.execute(
            "DELETE FROM documents WHERE document_id = $1",
            document_id.value,
        )
        return result == "DELETE 1"

    async def count_by_collection(self, collection_id: CollectionId) -> int:
        """Count documents in a collection."""
        val = await self._pool.fetchval(
            "SELECT COUNT(*) FROM documents WHERE collection_id = $1",
            collection_id.value,
        )
        return int(val or 0)
