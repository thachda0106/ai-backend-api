---
phase: 3
plan: 3
wave: 2
depends_on: ["3.1", "3.2"]
files_modified:
  - app/application/use_cases/process_document.py
autonomous: true

must_haves:
  truths:
    - "ProcessDocumentUseCase runs the full pipeline: chunk → embed → store"
    - "Uses IngestionJob FSM to track progress through stages"
    - "Stores embeddings in Qdrant via VectorRepository"
    - "Handles errors gracefully and marks job as FAILED"
---

# Plan 3.3: Document Processing Pipeline

## Objective
Implement the document processing pipeline — the background task that transforms a raw document into searchable vector embeddings. This is the core data pipeline: extract → chunk → embed → store.

## Context
- @app/domain/entities/ingestion_job.py — IngestionJob FSM (QUEUED→EXTRACTING→CHUNKING→EMBEDDING→STORING→COMPLETED)
- @app/domain/services/chunking_service.py — ChunkingStrategy, SimpleChunkingStrategy, ChunkData
- @app/domain/entities/chunk.py — Chunk entity with embedding
- @app/infrastructure/llm/openai_embedding.py — OpenAIEmbeddingService
- @app/infrastructure/vector_db/qdrant_adapter.py — QdrantVectorRepository
- @app/domain/repositories/chunk_repository.py — ChunkRepository ABC
- @app/infrastructure/token/tiktoken_service.py — TiktokenService
- @app/core/config/settings.py — ChunkingSettings (chunk_size, chunk_overlap)

## Tasks

<task type="auto">
  <name>Implement ProcessDocumentUseCase</name>
  <files>app/application/use_cases/process_document.py</files>
  <action>
    Create `ProcessDocumentUseCase`:
    
    Constructor (injected):
    - `document_repository`, `chunk_repository`, `vector_repository`
    - `embedding_provider` (EmbeddingProvider)
    - `chunking_strategy` (ChunkingStrategy)
    - `token_service` (TokenService)
    - `settings` (Settings — for chunking config)
    
    Method `async execute(document_id: DocumentId, job: IngestionJob) -> None`:
    
    Pipeline stages, using job FSM:
    
    1. **EXTRACTING**:
       - `job.advance_status(EXTRACTING)`
       - Fetch document from repository
       - Validate document has content
    
    2. **CHUNKING**:
       - `job.advance_status(CHUNKING)`
       - Call `chunking_strategy.chunk(document.content, chunk_size, overlap)`
       - Create `Chunk` entities from `ChunkData` results
       - Save chunks via `chunk_repository.save_many()`
       - `job.record_progress(0, len(chunks))`
    
    3. **EMBEDDING**:
       - `job.advance_status(EMBEDDING)`
       - Extract chunk contents as list[str]
       - Call `embedding_provider.embed_batch(texts)` 
       - Attach embeddings to chunks via `chunk.set_embedding()`
       - Update progress: `job.record_progress(i, total)`
    
    4. **STORING**:
       - `job.advance_status(STORING)`
       - Build payload entries: `(chunk_id, embedding, metadata)` for each chunk
       - Metadata should include: document_id, collection_id, content, chunk_index, document_title
       - Call `vector_repository.upsert_many(entries)`
    
    5. **COMPLETED**:
       - `job.complete()`
       - Update document: `document.mark_completed(chunk_count, total_tokens)`
       - Save updated document
    
    **Error handling:**
    - Wrap entire pipeline in try/except
    - On failure: `job.fail(str(error))`
    - Update document: `document.mark_failed(str(error))`
    - Log error with structlog
    
    **Batch embedding:** If there are many chunks (>50), batch in groups of 50 for the embedding API call.
  </action>
  <verify>python -m poetry run python -c "from app.application.use_cases.process_document import ProcessDocumentUseCase; print('OK')"</verify>
  <done>ProcessDocumentUseCase runs full pipeline with FSM tracking and error handling</done>
</task>

## Success Criteria
- [ ] Pipeline follows IngestionJob FSM stages correctly
- [ ] Chunks are created with correct metadata
- [ ] Embeddings are generated in batches and stored in Qdrant
- [ ] Errors are caught and job is marked FAILED
