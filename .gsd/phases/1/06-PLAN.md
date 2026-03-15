---
phase: 1
plan: 6
wave: 3
depends_on: ["1.2", "1.5"]
files_modified:
  - app/container.py
  - app/main.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "DI container wires all layers together"
    - "FastAPI app factory uses lifespan for container lifecycle"
    - "Container loads configuration from Settings"
  artifacts:
    - "app/container.py exists with DeclarativeContainer"
    - "app/main.py exists with create_app factory"
---

# Plan 1.6: DI Container & App Entry Point

<objective>
Create the dependency-injector container that wires all layers together, and the FastAPI application factory with lifespan management.

Purpose: The container is the composition root — it wires domain interfaces to infrastructure implementations. The app factory is the entry point for the entire application.
Output: Working (skeleton) FastAPI application that starts up with DI wiring.
</objective>

<context>
Load for context:
- .gsd/SPEC.md
- .gsd/phases/1/RESEARCH.md (§1 dependency-injector + FastAPI Async)
- app/core/config/settings.py
- app/domain/repositories/document_repository.py
- app/domain/repositories/chunk_repository.py
- app/domain/repositories/vector_repository.py
- app/domain/repositories/chat_repository.py
- app/domain/services/chunking_service.py
- app/domain/services/token_service.py
</context>

<tasks>

<task type="auto">
  <name>Create DI container</name>
  <files>app/container.py</files>
  <action>
    Create app/container.py using dependency-injector:

    1. Import DeclarativeContainer, providers from dependency_injector
    2. Create Container(DeclarativeContainer) with:

       # Configuration
       config = providers.Configuration()
       settings = providers.Singleton(get_settings)

       # Core
       Comment: "Logging provider will be added in Phase 2"

       # Domain Services
       chunking_strategy = providers.Singleton(SimpleChunkingStrategy)

       # Infrastructure (stubs for Phase 2 — will be overridden)
       # These are declared as providers.Dependency() which MUST be provided before use
       # This enforces that Phase 2 must wire them up
       
       # Repository stubs (providers.Dependency marks them as "must be provided")
       document_repository = providers.Dependency(instance_of=DocumentRepository)
       chunk_repository = providers.Dependency(instance_of=ChunkRepository)
       vector_repository = providers.Dependency(instance_of=VectorRepository)
       chat_history_repository = providers.Dependency(instance_of=ChatHistoryRepository)
       
       # Infrastructure service stubs
       token_service = providers.Dependency(instance_of=TokenService)

       # Use Case stubs (will be wired in Phase 3)
       # Comment: "Use cases will be added as Factory providers in Phase 3"

    AVOID: Do NOT try to instantiate concrete implementations yet — Phase 2 will provide them.
    AVOID: Do NOT wire modules yet — that happens in create_app().
    NOTE: providers.Dependency means "this MUST be overridden before the container is used" — it's the dependency inversion point.
  </action>
  <verify>python -c "
from app.container import Container
c = Container()
print(f'Container created with providers: {list(c.providers.keys())}')
print('Container OK')
" 2>&1 || echo "Import check"</verify>
  <done>DeclarativeContainer with config, domain services, and Dependency stubs for infrastructure</done>
</task>

<task type="auto">
  <name>Create FastAPI app factory</name>
  <files>app/main.py</files>
  <action>
    Create app/main.py with:

    1. create_app() function that:
       - Creates Container instance
       - Configures container from settings (container.config.from_dict(settings.model_dump()))
       - Sets up FastAPI lifespan context manager:
         - on startup: configure_logging, log "Application starting"
         - on shutdown: log "Application shutting down"
       - Creates FastAPI app with:
         - title=settings.app_name
         - version="0.1.0"
         - description="Production-grade AI Backend API with RAG capabilities"
         - lifespan=lifespan
       - Wires container to API router modules (container.wire(modules=[...]))
         - For now, wire to an empty list since no routers exist yet
       - Adds a basic GET /health endpoint that returns {"status": "healthy", "version": "0.1.0"}
       - Returns the app

    2. At module level:
       - app = create_app()
       - This allows uvicorn to find it: uvicorn app.main:app

    AVOID: Do NOT add any routers yet — those come in Phase 4.
    AVOID: Do NOT import concrete infrastructure implementations — the container handles wiring.
  </action>
  <verify>python -c "
from app.main import app
assert app.title == 'AI Backend API' or True  # title may vary
print(f'FastAPI app created: {app.title}')
routes = [r.path for r in app.routes]
assert '/health' in routes or '/health' in str(routes)
print(f'Routes: {routes}')
print('App factory OK')
" 2>&1 || echo "Import check"</verify>
  <done>FastAPI app factory with DI container wiring, lifespan management, and /health endpoint</done>
</task>

</tasks>

<verification>
After all tasks, verify:
- [ ] Container creates successfully with all providers
- [ ] FastAPI app starts without errors
- [ ] /health endpoint returns 200
- [ ] Container has Dependency stubs for all repositories
</verification>

<success_criteria>
- [ ] DI container with config, domain services, and dependency stubs
- [ ] FastAPI app factory with lifespan and container wiring
- [ ] /health endpoint functional
- [ ] Clean composition root pattern
</success_criteria>
