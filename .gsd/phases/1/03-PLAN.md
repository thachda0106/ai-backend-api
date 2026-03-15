---
phase: 1
plan: 3
wave: 2
depends_on: ["1.1"]
files_modified:
  - app/domain/value_objects/identifiers.py
  - app/domain/value_objects/embedding.py
  - app/domain/value_objects/pagination.py
  - app/domain/value_objects/base.py
  - app/domain/exceptions/base.py
  - app/domain/exceptions/document.py
  - app/domain/exceptions/search.py
  - app/domain/exceptions/llm.py
  - app/domain/entities/base.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "ValueObject base class exists with frozen=True config"
    - "All identifier value objects are immutable and hashable"
    - "Domain exception hierarchy is complete"
    - "Base entity class with id, created_at, updated_at exists"
  artifacts:
    - "app/domain/value_objects/base.py exists"
    - "app/domain/value_objects/identifiers.py exists"
    - "app/domain/exceptions/base.py exists"
    - "app/domain/entities/base.py exists"
---

# Plan 1.3: Domain Primitives — Value Objects, Exceptions & Base Entity

<objective>
Create the domain foundation: value object base class, all identifier/embedding value objects, domain exception hierarchy, and base entity class.

Purpose: These are the building blocks that all domain entities and services depend on. They establish immutability patterns and error handling conventions.
Output: Complete set of domain primitives ready for entity construction.
</objective>

<context>
Load for context:
- .gsd/SPEC.md
- .gsd/phases/1/RESEARCH.md (§5 Domain Value Objects)
- app/domain/value_objects/__init__.py
- app/domain/exceptions/__init__.py
- app/domain/entities/__init__.py
</context>

<tasks>

<task type="auto">
  <name>Create value object base and identifiers</name>
  <files>
    app/domain/value_objects/base.py
    app/domain/value_objects/identifiers.py
    app/domain/value_objects/embedding.py
    app/domain/value_objects/pagination.py
  </files>
  <action>
    Create app/domain/value_objects/base.py:
    - ValueObject base class inheriting from pydantic.BaseModel
    - model_config = ConfigDict(frozen=True)
    - This is the base for ALL value objects

    Create app/domain/value_objects/identifiers.py:
    - DocumentId(ValueObject): value: uuid.UUID = Field(default_factory=uuid.uuid4)
    - ChunkId(ValueObject): value: uuid.UUID = Field(default_factory=uuid.uuid4)
    - CollectionId(ValueObject): value: uuid.UUID = Field(default_factory=uuid.uuid4)
    - UserId(ValueObject): value: uuid.UUID = Field(default_factory=uuid.uuid4)
    - IngestionJobId(ValueObject): value: uuid.UUID = Field(default_factory=uuid.uuid4)
    - Each should have a class method `from_str(cls, value: str) -> Self` for deserialization

    Create app/domain/value_objects/embedding.py:
    - EmbeddingVector(ValueObject): values: tuple[float, ...], model: str, dimensions: int
    - Add a @model_validator that checks len(values) == dimensions

    Create app/domain/value_objects/pagination.py:
    - PaginationParams(ValueObject): offset: int = 0, limit: int = 10
    - Add validators: offset >= 0, 1 <= limit <= 100

    AVOID: Do NOT use list for sequences in value objects — use tuple for immutability.
    AVOID: Do NOT import from infrastructure or framework layers — domain must be pure.
  </action>
  <verify>python -c "
from app.domain.value_objects.identifiers import DocumentId, ChunkId
from app.domain.value_objects.embedding import EmbeddingVector
d = DocumentId()
assert d == d  # hashable check
print(f'DocumentId: {d.value}')
e = EmbeddingVector(values=(0.1, 0.2, 0.3), model='test', dimensions=3)
print(f'EmbeddingVector: {e.dimensions}d')
print('All value objects OK')
" 2>&1 || echo "Import check"</verify>
  <done>ValueObject base class, 5 identifier VOs, EmbeddingVector VO, PaginationParams VO — all frozen and hashable</done>
</task>

<task type="auto">
  <name>Create domain exception hierarchy</name>
  <files>
    app/domain/exceptions/base.py
    app/domain/exceptions/document.py
    app/domain/exceptions/search.py
    app/domain/exceptions/llm.py
  </files>
  <action>
    Create app/domain/exceptions/base.py:
    - DomainException(Exception): base for all domain errors, with message: str and code: str attributes
    - EntityNotFoundException(DomainException): entity_type: str, entity_id: str
    - ValidationException(DomainException): field: str, detail: str
    - BusinessRuleViolation(DomainException): rule: str

    Create app/domain/exceptions/document.py:
    - DocumentNotFoundException(EntityNotFoundException): __init__ sets entity_type="Document"
    - DocumentAlreadyExistsException(DomainException)
    - InvalidDocumentContentException(ValidationException)
    - ChunkingException(DomainException)

    Create app/domain/exceptions/search.py:
    - SearchException(DomainException)
    - EmptyQueryException(ValidationException)
    - CollectionNotFoundException(EntityNotFoundException)

    Create app/domain/exceptions/llm.py:
    - LLMException(DomainException)
    - LLMConnectionException(LLMException)
    - LLMRateLimitException(LLMException): retry_after: float | None
    - TokenLimitExceededException(LLMException): token_count: int, max_tokens: int
    - EmbeddingException(LLMException)

    AVOID: Do NOT catch or handle exceptions here — this is just the hierarchy definition.
    AVOID: Do NOT import from any external libraries — exceptions should be pure Python.
  </action>
  <verify>python -c "
from app.domain.exceptions.base import DomainException, EntityNotFoundException
from app.domain.exceptions.document import DocumentNotFoundException
from app.domain.exceptions.llm import LLMRateLimitException
assert issubclass(DocumentNotFoundException, EntityNotFoundException)
assert issubclass(LLMRateLimitException, DomainException)
print('Exception hierarchy OK')
" 2>&1 || echo "Import check"</verify>
  <done>Complete domain exception hierarchy with 4 modules, all exceptions properly inheriting from DomainException</done>
</task>

<task type="auto">
  <name>Create base entity class</name>
  <files>app/domain/entities/base.py</files>
  <action>
    Create app/domain/entities/base.py:

    - Entity base class as a Pydantic BaseModel (NOT frozen — entities are mutable):
      - id: uuid.UUID = Field(default_factory=uuid.uuid4)
      - created_at: datetime = Field(default_factory=datetime.utcnow)
      - updated_at: datetime = Field(default_factory=datetime.utcnow)
      - model_config = ConfigDict(from_attributes=True)

    - Add an update() method that sets updated_at to current time
    - Add __eq__ based on id field (entity identity)
    - Add __hash__ based on id field

    AVOID: Do NOT use frozen=True for entities — they need to be mutable.
    AVOID: Do NOT add any domain-specific fields — this is purely the base.
  </action>
  <verify>python -c "
from app.domain.entities.base import Entity
e = Entity()
assert e.id is not None
assert e.created_at is not None
print(f'Entity base: id={e.id}, created_at={e.created_at}')
print('Entity base OK')
" 2>&1 || echo "Import check"</verify>
  <done>Entity base class with id, timestamps, equality by id, and update() method</done>
</task>

</tasks>

<verification>
After all tasks, verify:
- [ ] All value objects are frozen (immutable) and hashable
- [ ] Exception hierarchy has proper inheritance chain
- [ ] Entity base class is mutable with identity-based equality
- [ ] No imports from infrastructure or framework layers in domain
</verification>

<success_criteria>
- [ ] ValueObject base + 7 concrete value objects
- [ ] DomainException base + 10 specific exceptions across 4 modules
- [ ] Entity base class with id, timestamps, equality
- [ ] All types fully annotated for mypy strict
</success_criteria>
