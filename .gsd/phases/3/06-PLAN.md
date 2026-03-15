---
phase: 3
plan: 6
wave: 3
depends_on: ["3.2", "3.3", "3.4", "3.5"]
files_modified:
  - app/container.py
  - app/application/use_cases/ingest_document.py
autonomous: true

must_haves:
  truths:
    - "All use cases wired as Factory providers in DI container"
    - "IngestDocumentUseCase enqueues the real ProcessDocumentUseCase"
    - "Container verification passes with all application-layer providers"
---

# Plan 3.6: Container Wiring + Pipeline Integration

## Objective
Wire all Phase 3 use cases and application services into the DI container as Factory providers. Connect the ingestion use case to the real processing pipeline (replace the placeholder from Plan 3.2).

## Context
- @app/container.py — Current container with infrastructure providers
- All Phase 3 use cases and services from Plans 3.1-3.5

## Tasks

<task type="auto">
  <name>Wire use cases and services into DI container</name>
  <files>app/container.py</files>
  <action>
    Add to Container class:
    
    ```python
    # Application Services - Singletons
    prompt_service = providers.Singleton(PromptService)
    context_service = providers.Singleton(
        ContextService,
        token_service=token_service,
        max_context_tokens=...,  # from settings or default 3000
    )
    
    # Use Cases - Factory (new instance per request)
    ingest_document = providers.Factory(
        IngestDocumentUseCase,
        document_repository=document_repository,
        background_worker=background_worker,
    )
    
    process_document = providers.Factory(
        ProcessDocumentUseCase,
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        vector_repository=vector_repository,
        embedding_provider=embedding_provider,
        chunking_strategy=chunking_strategy,
        token_service=token_service,
        settings=settings,
    )
    
    search_documents = providers.Factory(
        SearchDocumentsUseCase,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        token_service=token_service,
    )
    
    rag_chat = providers.Factory(
        RAGChatUseCase,
        search_use_case=search_documents,
        chat_provider=chat_provider,
        prompt_service=prompt_service,
        context_service=context_service,
        chat_history_repository=chat_history_repository,
        token_service=token_service,
    )
    ```
    
    Add imports for all application layer classes.
  </action>
  <verify>OPENAI__API_KEY=test python -m poetry run python -c "from app.container import Container; c=Container(); assert 'ingest_document' in c.providers; assert 'process_document' in c.providers; assert 'search_documents' in c.providers; assert 'rag_chat' in c.providers; assert 'prompt_service' in c.providers; assert 'context_service' in c.providers; print(f'Container: {len(list(c.providers.keys()))} providers'); print('OK')"</verify>
  <done>Container has all use case and service providers wired</done>
</task>

<task type="auto">
  <name>Connect ingestion to real processing pipeline</name>
  <files>app/application/use_cases/ingest_document.py</files>
  <action>
    Update `IngestDocumentUseCase`:
    - Add `process_document_use_case: ProcessDocumentUseCase` as dependency
    - In `execute()`, instead of enqueueing a placeholder, enqueue:
      `self._worker.enqueue(self._process.execute(doc.document_id, job), task_name=str(job.job_id.value))`
    
    This connects the full pipeline: ingest → enqueue → process (chunk → embed → store).
  </action>
  <verify>OPENAI__API_KEY=test python -m poetry run python -c "from app.application.use_cases.ingest_document import IngestDocumentUseCase; import inspect; sig = inspect.signature(IngestDocumentUseCase.__init__); print(f'Params: {list(sig.parameters.keys())}'); print('OK')"</verify>
  <done>Ingestion use case enqueues real processing pipeline</done>
</task>

## Success Criteria
- [ ] All use cases wired as Factory providers (new per request)
- [ ] Application services wired as Singletons
- [ ] Ingestion → Processing pipeline is fully connected
- [ ] Container verification passes
