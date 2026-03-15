---
phase: 1
plan: 4
wave: 2
depends_on: ["1.3"]
files_modified:
  - app/domain/entities/document.py
  - app/domain/entities/chunk.py
  - app/domain/entities/collection.py
  - app/domain/entities/user.py
  - app/domain/entities/ingestion_job.py
  - app/domain/entities/search_result.py
  - app/domain/entities/chat.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "All domain entities inherit from Entity base class"
    - "Entities use value object identifiers (DocumentId, ChunkId, etc.)"
    - "Document and Chunk entities model the RAG pipeline data"
    - "IngestionJob tracks pipeline processing status"
  artifacts:
    - "app/domain/entities/document.py exists"
    - "app/domain/entities/chunk.py exists"
    - "app/domain/entities/collection.py exists"
    - "app/domain/entities/user.py exists"
    - "app/domain/entities/ingestion_job.py exists"
---

# Plan 1.4: Domain Entities

<objective>
Implement all domain entities for the RAG platform: Document, Chunk, Collection, User, IngestionJob, SearchResult, and ChatMessage.

Purpose: These entities model the core business concepts of the RAG pipeline and form the foundation for all use cases.
Output: Complete set of domain entities with proper relationships and business rules.
</objective>

<context>
Load for context:
- .gsd/SPEC.md
- .gsd/phases/1/RESEARCH.md (§5 Domain Value Objects, for patterns)
- app/domain/entities/base.py (Entity base class from Plan 1.3)
- app/domain/value_objects/identifiers.py (ID types from Plan 1.3)
- app/domain/value_objects/embedding.py (EmbeddingVector from Plan 1.3)
</context>

<tasks>

<task type="auto">
  <name>Create Document, Chunk, and Collection entities</name>
  <files>
    app/domain/entities/document.py
    app/domain/entities/chunk.py
    app/domain/entities/collection.py
  </files>
  <action>
    Create app/domain/entities/document.py:
    - DocumentStatus(str, Enum): PENDING, PROCESSING, COMPLETED, FAILED
    - Document(Entity):
      - document_id: DocumentId (use this as the domain identifier, separate from Entity.id)
      - collection_id: CollectionId
      - title: str
      - content: str
      - content_type: str = "text/plain"
      - metadata: dict[str, Any] = Field(default_factory=dict)
      - status: DocumentStatus = DocumentStatus.PENDING
      - chunk_count: int = 0
      - token_count: int = 0
      - error_message: str | None = None
      - Add method: mark_processing() -> sets status to PROCESSING, calls update()
      - Add method: mark_completed(chunk_count: int, token_count: int) -> sets status, counts, calls update()
      - Add method: mark_failed(error: str) -> sets status to FAILED, error_message, calls update()

    Create app/domain/entities/chunk.py:
    - Chunk(Entity):
      - chunk_id: ChunkId
      - document_id: DocumentId
      - collection_id: CollectionId
      - content: str
      - chunk_index: int (position within document)
      - start_char: int (character offset in original document)
      - end_char: int
      - token_count: int = 0
      - embedding: EmbeddingVector | None = None
      - metadata: dict[str, Any] = Field(default_factory=dict)
      - Add method: set_embedding(embedding: EmbeddingVector) -> sets embedding, calls update()
      - Add method: has_embedding() -> bool

    Create app/domain/entities/collection.py:
    - Collection(Entity):
      - collection_id: CollectionId
      - name: str
      - description: str = ""
      - document_count: int = 0
      - metadata: dict[str, Any] = Field(default_factory=dict)
      - Add method: increment_document_count() and decrement_document_count()

    AVOID: Do NOT add any persistence logic — entities are pure domain objects.
    AVOID: Do NOT import from infrastructure — use only domain value objects.
  </action>
  <verify>python -c "
from app.domain.entities.document import Document, DocumentStatus
from app.domain.entities.chunk import Chunk
from app.domain.entities.collection import Collection
from app.domain.value_objects.identifiers import DocumentId, CollectionId, ChunkId

cid = CollectionId()
did = DocumentId()
doc = Document(document_id=did, collection_id=cid, title='Test', content='Hello world')
assert doc.status == DocumentStatus.PENDING
doc.mark_processing()
assert doc.status == DocumentStatus.PROCESSING
print('Document, Chunk, Collection entities OK')
" 2>&1 || echo "Import check"</verify>
  <done>Document (with status transitions), Chunk (with embedding support), Collection entities — all using domain value objects</done>
</task>

<task type="auto">
  <name>Create User, IngestionJob, SearchResult, and ChatMessage entities</name>
  <files>
    app/domain/entities/user.py
    app/domain/entities/ingestion_job.py
    app/domain/entities/search_result.py
    app/domain/entities/chat.py
  </files>
  <action>
    Create app/domain/entities/user.py:
    - User(Entity):
      - user_id: UserId
      - name: str
      - email: str | None = None
      - total_tokens_used: int = 0
      - total_requests: int = 0
      - metadata: dict[str, Any] = Field(default_factory=dict)
      - Add method: track_usage(tokens: int) -> increments totals, calls update()

    Create app/domain/entities/ingestion_job.py:
    - IngestionStatus(str, Enum): QUEUED, EXTRACTING, CHUNKING, EMBEDDING, STORING, COMPLETED, FAILED
    - IngestionJob(Entity):
      - job_id: IngestionJobId
      - document_id: DocumentId
      - status: IngestionStatus = IngestionStatus.QUEUED
      - total_chunks: int = 0
      - processed_chunks: int = 0
      - error_message: str | None = None
      - started_at: datetime | None = None
      - completed_at: datetime | None = None
      - Add method: advance_status(new_status: IngestionStatus) -> validates transition, updates
      - Add method: record_progress(processed: int, total: int) -> updates chunk counts
      - Add method: fail(error: str) -> marks as FAILED with error
      - Add method: complete() -> marks as COMPLETED with completed_at
      - Add property: progress -> float (processed_chunks / total_chunks if total > 0, else 0)

    Create app/domain/entities/search_result.py (NOT an Entity — a domain data class):
    - SearchResult(BaseModel, frozen=True):
      - chunk_id: ChunkId
      - document_id: DocumentId
      - collection_id: CollectionId
      - content: str
      - score: float (similarity score, 0-1)
      - metadata: dict[str, Any] = Field(default_factory=dict)
      - document_title: str = ""
      - chunk_index: int = 0

    Create app/domain/entities/chat.py:
    - MessageRole(str, Enum): SYSTEM, USER, ASSISTANT
    - ChatMessage(BaseModel, frozen=True):
      - role: MessageRole
      - content: str
      - metadata: dict[str, Any] = Field(default_factory=dict)
    - ChatResponse(BaseModel):
      - message: ChatMessage
      - sources: list[SearchResult] = Field(default_factory=list)
      - token_usage: TokenUsage | None = None
    - TokenUsage(BaseModel, frozen=True):
      - prompt_tokens: int
      - completion_tokens: int
      - total_tokens: int
      - estimated_cost: float = 0.0

    AVOID: SearchResult and ChatMessage are value-like objects — use frozen=True, they are NOT entities.
    AVOID: Do NOT add any streaming logic to ChatMessage — that belongs in the application layer.
  </action>
  <verify>python -c "
from app.domain.entities.user import User
from app.domain.entities.ingestion_job import IngestionJob, IngestionStatus
from app.domain.entities.search_result import SearchResult
from app.domain.entities.chat import ChatMessage, MessageRole, TokenUsage
from app.domain.value_objects.identifiers import UserId, IngestionJobId, DocumentId, ChunkId, CollectionId

user = User(user_id=UserId(), name='Test')
user.track_usage(100)
assert user.total_tokens_used == 100

job = IngestionJob(job_id=IngestionJobId(), document_id=DocumentId())
assert job.status == IngestionStatus.QUEUED

msg = ChatMessage(role=MessageRole.USER, content='Hello')
assert msg.content == 'Hello'

print('User, IngestionJob, SearchResult, ChatMessage OK')
" 2>&1 || echo "Import check"</verify>
  <done>User (with usage tracking), IngestionJob (with status machine), SearchResult, ChatMessage/ChatResponse/TokenUsage</done>
</task>

</tasks>

<verification>
After all tasks, verify:
- [ ] Document has proper status transitions (PENDING→PROCESSING→COMPLETED/FAILED)
- [ ] Chunk supports optional embedding attachment
- [ ] IngestionJob tracks progress with status machine
- [ ] User tracks token usage
- [ ] SearchResult and ChatMessage are frozen (immutable)
- [ ] No infrastructure imports in domain entities
</verification>

<success_criteria>
- [ ] 5 entity classes (Document, Chunk, Collection, User, IngestionJob)
- [ ] 3 domain data classes (SearchResult, ChatMessage, ChatResponse)
- [ ] 1 supporting value object (TokenUsage)
- [ ] All entities use domain value object identifiers
- [ ] Business rules encoded in entity methods
</success_criteria>
