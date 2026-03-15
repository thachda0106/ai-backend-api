---
phase: 2
plan: 5
wave: 3
depends_on: ["2.1", "2.3"]
files_modified:
  - app/infrastructure/repositories/__init__.py
  - app/infrastructure/repositories/memory_document_repo.py
  - app/infrastructure/repositories/memory_chunk_repo.py
  - app/infrastructure/repositories/redis_chat_repo.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "In-memory DocumentRepository for development/testing"
    - "In-memory ChunkRepository for development/testing"
    - "Redis-backed ChatHistoryRepository for persistence"
    - "All implement their respective ABCs from domain layer"
---

# Plan 2.5: Repository Implementations

## Objective
Implement concrete repository classes that fulfill the domain ABCs. In-memory versions for Document and Chunk (sufficient for dev/testing — Phase 6 can add database-backed). Redis-backed for ChatHistory (needs persistence across requests).

## Context
- @app/domain/repositories/document_repository.py — DocumentRepository ABC
- @app/domain/repositories/chunk_repository.py — ChunkRepository ABC
- @app/domain/repositories/chat_repository.py — ChatHistoryRepository ABC
- @app/domain/entities/document.py — Document entity
- @app/domain/entities/chunk.py — Chunk entity
- @app/domain/entities/chat.py — ChatMessage

## Tasks

<task type="auto">
  <name>Implement in-memory document and chunk repositories</name>
  <files>
    app/infrastructure/repositories/__init__.py
    app/infrastructure/repositories/memory_document_repo.py
    app/infrastructure/repositories/memory_chunk_repo.py
  </files>
  <action>
    1. Create `app/infrastructure/repositories/__init__.py` with docstring.
    
    2. `InMemoryDocumentRepository(DocumentRepository)`:
       - Internal store: `dict[str, Document]` keyed by document_id string
       - Implement all ABC methods: get_by_id, get_by_collection (with pagination), save, update, delete, count_by_collection
       - Thread-safe using asyncio.Lock
    
    3. `InMemoryChunkRepository(ChunkRepository)`:
       - Internal store: `dict[str, Chunk]` keyed by chunk_id string
       - Implement: get_by_id, get_by_document, save_many, delete_by_document, count_by_document
       - Thread-safe using asyncio.Lock
    
    These are development/testing implementations. Production would use PostgreSQL or similar.
  </action>
  <verify>python -m poetry run python -c "from app.infrastructure.repositories.memory_document_repo import InMemoryDocumentRepository; from app.infrastructure.repositories.memory_chunk_repo import InMemoryChunkRepository; print('OK')"</verify>
  <done>Both in-memory repositories implement their ABCs</done>
</task>

<task type="auto">
  <name>Implement Redis-backed chat history repository</name>
  <files>app/infrastructure/repositories/redis_chat_repo.py</files>
  <action>
    `RedisChatHistoryRepository(ChatHistoryRepository)`:
    
    Constructor:
    - Takes `redis_cache: RedisCache`
    
    Methods:
    1. `save_message(user_id, message)`:
       - Key: `chat:{user_id}`
       - RPUSH the JSON-serialized message to a Redis list
       - LTRIM to keep max 100 messages (prevent unbounded growth)
    
    2. `get_history(user_id, limit)`:
       - LRANGE to get last `limit` messages
       - Deserialize and return as list[ChatMessage]
    
    3. `clear_history(user_id)`:
       - DEL the key
    
    Use the RedisCache's underlying redis client for list operations.
  </action>
  <verify>python -m poetry run python -c "from app.infrastructure.repositories.redis_chat_repo import RedisChatHistoryRepository; print('OK')"</verify>
  <done>RedisChatHistoryRepository persists chat history in Redis lists</done>
</task>

## Success Criteria
- [ ] `InMemoryDocumentRepository` fully implements `DocumentRepository` ABC
- [ ] `InMemoryChunkRepository` fully implements `ChunkRepository` ABC
- [ ] `RedisChatHistoryRepository` fully implements `ChatHistoryRepository` ABC
- [ ] In-memory repos are thread-safe with asyncio.Lock
