---
phase: 2
plan: 3
wave: 2
depends_on: ["2.1"]
files_modified:
  - app/infrastructure/vector_db/qdrant_adapter.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "QdrantVectorRepository implements VectorRepository ABC"
    - "Uses qdrant_client.AsyncQdrantClient for async operations"
    - "Supports upsert, upsert_many, search, delete operations"
    - "ensure_collection creates collection with correct vector config"
---

# Plan 2.3: Qdrant Vector Store Adapter

## Objective
Implement the Qdrant adapter that fulfills the `VectorRepository` ABC. This is the persistence layer for vector embeddings — essential for semantic search in the RAG pipeline.

## Context
- @app/domain/repositories/vector_repository.py — VectorRepository ABC
- @app/domain/value_objects/embedding.py — EmbeddingVector
- @app/domain/value_objects/identifiers.py — ChunkId, DocumentId
- @app/domain/entities/search_result.py — SearchResult
- @app/core/config/settings.py — QdrantSettings (host, port, grpc_port, collection_name, prefer_grpc)

## Tasks

<task type="auto">
  <name>Implement QdrantVectorRepository</name>
  <files>app/infrastructure/vector_db/qdrant_adapter.py</files>
  <action>
    Implement `QdrantVectorRepository(VectorRepository)`:
    
    Constructor:
    - Takes `settings: QdrantSettings`
    - Creates `qdrant_client.AsyncQdrantClient(host=..., port=..., grpc_port=..., prefer_grpc=...)`
    
    Methods:
    1. `upsert(chunk_id, embedding, metadata)`:
       - Convert chunk_id to string for point ID
       - Use `client.upsert(collection_name, points=[PointStruct(...)])`
    
    2. `upsert_many(entries)`:
       - Batch upsert with list of PointStruct
       - Use `client.upsert(collection_name, points=[...])`
    
    3. `search(query_embedding, top_k, filters)`:
       - Call `client.query_points()` or `client.search()`
       - Convert Qdrant ScoredPoints to domain `SearchResult` objects
       - Apply filters if provided (qdrant Filter/FieldCondition)
    
    4. `delete(chunk_id)`:
       - Delete by point ID
    
    5. `delete_by_document(document_id)`:
       - Use payload filter: `document_id == str(document_id)`
       - Call `client.delete(collection_name, points_selector=FilterSelector(...))`
    
    6. `ensure_collection(collection_name, vector_size)`:
       - Check if collection exists via `client.collection_exists()`
       - If not, create with `VectorParams(size=vector_size, distance=Cosine)`
    
    Error handling:
    - Map qdrant exceptions to domain exceptions where appropriate
    - Log all operations with structlog (collection, count, latency)
    
    AVOID: Don't hardcode collection names — always use the configured value.
  </action>
  <verify>python -m poetry run python -c "from app.infrastructure.vector_db.qdrant_adapter import QdrantVectorRepository; print('OK')"</verify>
  <done>QdrantVectorRepository implements all 6 methods of VectorRepository ABC</done>
</task>

## Success Criteria
- [ ] `QdrantVectorRepository` fully implements `VectorRepository` ABC
- [ ] Uses `AsyncQdrantClient` for non-blocking operations
- [ ] Converts between Qdrant types and domain types cleanly
- [ ] `ensure_collection` is idempotent (safe to call multiple times)
