---
phase: 1
plan: 5
wave: 3
depends_on: ["1.3", "1.4"]
files_modified:
  - app/domain/repositories/document_repository.py
  - app/domain/repositories/chunk_repository.py
  - app/domain/repositories/vector_repository.py
  - app/domain/repositories/chat_repository.py
  - app/domain/services/chunking_service.py
  - app/domain/services/token_service.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "All repositories are abstract (ABC) with async methods"
    - "Repository interfaces define CRUD + domain-specific operations"
    - "Domain services contain pure business logic with no infrastructure deps"
    - "ChunkingService defines the chunking contract"
  artifacts:
    - "app/domain/repositories/document_repository.py exists"
    - "app/domain/repositories/vector_repository.py exists"
    - "app/domain/services/chunking_service.py exists"
---

# Plan 1.5: Repository Interfaces & Domain Services

<objective>
Define all abstract repository interfaces and domain services. These establish the contracts that infrastructure implementations must fulfill.

Purpose: Repository interfaces are the dependency inversion boundary — domain defines what it needs, infrastructure provides how.
Output: 4 repository ABCs and 2 domain services.
</objective>

<context>
Load for context:
- .gsd/SPEC.md
- app/domain/entities/document.py
- app/domain/entities/chunk.py
- app/domain/entities/search_result.py
- app/domain/entities/chat.py
- app/domain/value_objects/identifiers.py
- app/domain/value_objects/embedding.py
- app/domain/value_objects/pagination.py
</context>

<tasks>

<task type="auto">
  <name>Create repository interfaces</name>
  <files>
    app/domain/repositories/document_repository.py
    app/domain/repositories/chunk_repository.py
    app/domain/repositories/vector_repository.py
    app/domain/repositories/chat_repository.py
  </files>
  <action>
    All repositories are ABCs (from abc import ABC, abstractmethod) with async methods.

    Create app/domain/repositories/document_repository.py:
    - DocumentRepository(ABC):
      - async get_by_id(document_id: DocumentId) -> Document | None
      - async get_by_collection(collection_id: CollectionId, pagination: PaginationParams) -> list[Document]
      - async save(document: Document) -> Document
      - async update(document: Document) -> Document
      - async delete(document_id: DocumentId) -> bool
      - async count_by_collection(collection_id: CollectionId) -> int

    Create app/domain/repositories/chunk_repository.py:
    - ChunkRepository(ABC):
      - async get_by_id(chunk_id: ChunkId) -> Chunk | None
      - async get_by_document(document_id: DocumentId) -> list[Chunk]
      - async save_many(chunks: list[Chunk]) -> list[Chunk]
      - async delete_by_document(document_id: DocumentId) -> int
      - async count_by_document(document_id: DocumentId) -> int

    Create app/domain/repositories/vector_repository.py:
    - VectorRepository(ABC):
      - async upsert(chunk_id: ChunkId, embedding: EmbeddingVector, metadata: dict[str, Any]) -> None
      - async upsert_many(entries: list[tuple[ChunkId, EmbeddingVector, dict[str, Any]]]) -> None
      - async search(query_embedding: EmbeddingVector, top_k: int = 10, filters: dict[str, Any] | None = None) -> list[SearchResult]
      - async delete(chunk_id: ChunkId) -> bool
      - async delete_by_document(document_id: DocumentId) -> int
      - async ensure_collection(collection_name: str, vector_size: int) -> None

    Create app/domain/repositories/chat_repository.py:
    - ChatHistoryRepository(ABC):
      - async save_message(user_id: UserId, message: ChatMessage) -> None
      - async get_history(user_id: UserId, limit: int = 10) -> list[ChatMessage]
      - async clear_history(user_id: UserId) -> None

    AVOID: Do NOT add any implementation — these are PURE abstractions.
    AVOID: Do NOT import from infrastructure layer.
    AVOID: Do NOT use SQLAlchemy or any ORM types in signatures — use domain types only.
  </action>
  <verify>python -c "
from app.domain.repositories.document_repository import DocumentRepository
from app.domain.repositories.chunk_repository import ChunkRepository
from app.domain.repositories.vector_repository import VectorRepository
from app.domain.repositories.chat_repository import ChatHistoryRepository
import inspect

# Verify they are ABCs
assert inspect.isabstract(DocumentRepository)
assert inspect.isabstract(ChunkRepository)
assert inspect.isabstract(VectorRepository)
assert inspect.isabstract(ChatHistoryRepository)

# Verify async methods
assert inspect.iscoroutinefunction(DocumentRepository.get_by_id)
print('All 4 repository interfaces are abstract with async methods')
" 2>&1 || echo "Import check"</verify>
  <done>4 abstract repository interfaces with async methods using only domain types</done>
</task>

<task type="auto">
  <name>Create domain services</name>
  <files>
    app/domain/services/chunking_service.py
    app/domain/services/token_service.py
  </files>
  <action>
    Create app/domain/services/chunking_service.py:
    - ChunkingStrategy(ABC):
      - abstractmethod chunk(content: str, chunk_size: int, chunk_overlap: int) -> list[ChunkData]
    - ChunkData(BaseModel, frozen=True):
      - content: str
      - start_char: int
      - end_char: int
      - chunk_index: int
      - token_count: int
    - SimpleChunkingStrategy(ChunkingStrategy):
      - Implements basic text chunking by separator (e.g., newline)
      - Respects chunk_size (in characters) and chunk_overlap
      - Returns list of ChunkData with positions

    Create app/domain/services/token_service.py:
    - TokenService(ABC):
      - abstractmethod count_tokens(text: str, model: str) -> int
      - abstractmethod estimate_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float
      - abstractmethod truncate_to_token_limit(text: str, max_tokens: int, model: str) -> str

    SimpleChunkingStrategy is the ONLY concrete implementation in domain — it's pure business logic.
    TokenService is abstract — its implementation (using tiktoken) will be in infrastructure.

    AVOID: Do NOT import tiktoken in domain — token counting implementation is infrastructure.
    AVOID: Do NOT call external APIs from domain services.
  </action>
  <verify>python -c "
from app.domain.services.chunking_service import SimpleChunkingStrategy, ChunkData
from app.domain.services.token_service import TokenService
import inspect

# Test chunking
chunker = SimpleChunkingStrategy()
chunks = chunker.chunk('Line 1\nLine 2\nLine 3\nLine 4', chunk_size=20, chunk_overlap=5)
assert len(chunks) > 0
assert all(isinstance(c, ChunkData) for c in chunks)
print(f'SimpleChunkingStrategy produced {len(chunks)} chunks')

# Verify TokenService is abstract
assert inspect.isabstract(TokenService)
print('Domain services OK')
" 2>&1 || echo "Import check"</verify>
  <done>ChunkingStrategy ABC + SimpleChunkingStrategy implementation, TokenService ABC, ChunkData value object</done>
</task>

</tasks>

<verification>
After all tasks, verify:
- [ ] All 4 repositories are abstract (cannot be instantiated)
- [ ] All repository methods are async
- [ ] Repository signatures use only domain types
- [ ] SimpleChunkingStrategy produces valid ChunkData
- [ ] TokenService is abstract (no tiktoken import in domain)
</verification>

<success_criteria>
- [ ] 4 repository ABCs: Document, Chunk, Vector, ChatHistory
- [ ] ChunkingStrategy ABC + concrete SimpleChunkingStrategy
- [ ] TokenService ABC
- [ ] ChunkData value object
- [ ] Zero infrastructure dependencies in domain layer
</success_criteria>
