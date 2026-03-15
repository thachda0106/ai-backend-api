---
phase: 3
plan: 2
wave: 1
depends_on: []
files_modified:
  - app/application/use_cases/ingest_document.py
autonomous: true

must_haves:
  truths:
    - "IngestDocumentUseCase saves document and enqueues background processing"
    - "Returns IngestDocumentResponse with document_id and job_id"
    - "Triggers processing pipeline via BackgroundWorker"
---

# Plan 3.2: Document Ingestion Use Case

## Objective
Implement the document ingestion use case — the entry point for adding documents to the RAG system. It saves the document, creates an ingestion job, and enqueues background processing.

## Context
- @app/domain/entities/document.py — Document entity with status FSM
- @app/domain/entities/ingestion_job.py — IngestionJob with 7-stage FSM
- @app/domain/repositories/document_repository.py — DocumentRepository ABC
- @app/infrastructure/queue/worker.py — BackgroundWorker
- @app/application/dto/document.py — IngestDocumentRequest/Response (from Plan 3.1)

## Tasks

<task type="auto">
  <name>Implement IngestDocumentUseCase</name>
  <files>app/application/use_cases/ingest_document.py</files>
  <action>
    Create `IngestDocumentUseCase`:
    
    Constructor (injected dependencies):
    - `document_repository: DocumentRepository`
    - `background_worker: BackgroundWorker`
    
    Method `async execute(request: IngestDocumentRequest) -> IngestDocumentResponse`:
    1. Create `Document` from request data:
       - Generate `DocumentId()`
       - Set `collection_id` (from request or default)
       - Set title, content
       - Status starts as PENDING
    2. Save document via repository
    3. Create `IngestionJob(document_id=doc.document_id)`
    4. Mark document as PROCESSING
    5. Update document in repository
    6. Enqueue processing pipeline coroutine via `background_worker.enqueue()`
       - The processing pipeline itself is Plan 3.3 — for now, enqueue a placeholder
       - Pass `job_id` as task_name for traceability
    7. Return `IngestDocumentResponse(document_id, job_id, status="processing")`
    
    Log all steps with structlog.
    
    IMPORTANT: The use case should NOT contain the processing pipeline logic itself.
    It only triggers it via the background worker.
  </action>
  <verify>python -m poetry run python -c "from app.application.use_cases.ingest_document import IngestDocumentUseCase; print('OK')"</verify>
  <done>IngestDocumentUseCase importable with execute() method</done>
</task>

## Success Criteria
- [ ] `IngestDocumentUseCase.execute()` saves document and returns response DTO
- [ ] Processing is enqueued via BackgroundWorker (non-blocking)
- [ ] IngestionJob tracks the pipeline status
