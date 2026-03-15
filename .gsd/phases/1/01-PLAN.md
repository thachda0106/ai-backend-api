---
phase: 1
plan: 1
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - app/__init__.py
  - app/api/__init__.py
  - app/api/routers/__init__.py
  - app/api/dependencies/__init__.py
  - app/api/middleware/__init__.py
  - app/api/schemas/__init__.py
  - app/application/__init__.py
  - app/application/services/__init__.py
  - app/application/use_cases/__init__.py
  - app/application/dto/__init__.py
  - app/domain/__init__.py
  - app/domain/entities/__init__.py
  - app/domain/value_objects/__init__.py
  - app/domain/repositories/__init__.py
  - app/domain/services/__init__.py
  - app/domain/exceptions/__init__.py
  - app/infrastructure/__init__.py
  - app/infrastructure/llm/__init__.py
  - app/infrastructure/vector_db/__init__.py
  - app/infrastructure/cache/__init__.py
  - app/infrastructure/queue/__init__.py
  - app/core/__init__.py
  - app/core/config/__init__.py
  - app/core/logging/__init__.py
  - app/core/security/__init__.py
  - .gitignore
  - .env.example
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Poetry project initialized with pyproject.toml containing all dependencies"
    - "Clean Architecture directory structure exists with proper __init__.py files"
    - "ruff and mypy are configured in pyproject.toml"
    - ".gitignore and .env.example exist"
  artifacts:
    - "pyproject.toml exists with fastapi, pydantic, dependency-injector, etc."
    - "app/ directory tree matches Clean Architecture layout"
---

# Plan 1.1: Project Skeleton & Tooling

<objective>
Initialize the Poetry project with all production and dev dependencies, create the complete Clean Architecture directory structure, and configure ruff + mypy in pyproject.toml.

Purpose: This is the absolute foundation — every other plan depends on having a valid Python project with proper package structure.
Output: A Poetry-managed Python project with complete directory tree and tooling config.
</objective>

<context>
Load for context:
- .gsd/SPEC.md
- .gsd/phases/1/RESEARCH.md (§4 Poetry + Ruff + Mypy Configuration, §2 Project Structure)
</context>

<tasks>

<task type="auto">
  <name>Initialize Poetry project with dependencies</name>
  <files>pyproject.toml</files>
  <action>
    Initialize a Poetry project in the repo root. Create pyproject.toml with:

    [tool.poetry]
    - name = "ai-backend-api"
    - version = "0.1.0"
    - description = "Production-grade AI Backend API with RAG capabilities"
    - python = "^3.12"

    Production dependencies:
    - fastapi = "^0.115"
    - uvicorn = {version = "^0.34", extras = ["standard"]}
    - pydantic = "^2.10"
    - pydantic-settings = "^2.7"
    - dependency-injector = "^4.48"
    - openai = "^1.60"
    - qdrant-client = "^1.13"
    - redis = {version = "^5.2", extras = ["hiredis"]}
    - sse-starlette = "^2.2"
    - tiktoken = "^0.9"
    - httpx = "^0.28"
    - structlog = "^25.1"
    - python-multipart = "^0.0.18"

    Dev dependencies:
    - ruff = "^0.9"
    - mypy = "^1.14"
    - pytest = "^8.3"
    - pytest-asyncio = "^0.25"
    - pytest-cov = "^6.0"

    AVOID: Do NOT run `poetry install` yet — just create the pyproject.toml file.
    AVOID: Do NOT use `poetry init` interactively — write the file directly.
  </action>
  <verify>python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); assert 'fastapi' in str(d); print('OK')"</verify>
  <done>pyproject.toml exists with all dependencies listed, valid TOML syntax</done>
</task>

<task type="auto">
  <name>Create Clean Architecture directory structure</name>
  <files>
    app/__init__.py
    app/api/__init__.py
    app/api/routers/__init__.py
    app/api/dependencies/__init__.py
    app/api/middleware/__init__.py
    app/api/schemas/__init__.py
    app/application/__init__.py
    app/application/services/__init__.py
    app/application/use_cases/__init__.py
    app/application/dto/__init__.py
    app/domain/__init__.py
    app/domain/entities/__init__.py
    app/domain/value_objects/__init__.py
    app/domain/repositories/__init__.py
    app/domain/services/__init__.py
    app/domain/exceptions/__init__.py
    app/infrastructure/__init__.py
    app/infrastructure/llm/__init__.py
    app/infrastructure/vector_db/__init__.py
    app/infrastructure/cache/__init__.py
    app/infrastructure/queue/__init__.py
    app/core/__init__.py
    app/core/config/__init__.py
    app/core/logging/__init__.py
    app/core/security/__init__.py
    tests/__init__.py
    tests/unit/__init__.py
    tests/integration/__init__.py
  </files>
  <action>
    Create the entire directory tree with __init__.py files. Each __init__.py should contain a module docstring describing the layer/package purpose:

    - app/: "AI Backend API - Production-grade RAG platform"
    - app/api/: "API Layer - FastAPI routers, schemas, middleware"
    - app/application/: "Application Layer - Use cases and orchestration"
    - app/domain/: "Domain Layer - Core entities, value objects, business rules"
    - app/infrastructure/: "Infrastructure Layer - External service integrations"
    - app/core/: "Core - Cross-cutting concerns (config, logging, security)"
    - tests/: "Test suite"

    Sub-packages should have a brief docstring like:
    - app/domain/entities/: "Domain entities"
    - app/domain/value_objects/: "Immutable value objects"
    etc.

    AVOID: Do NOT put any implementation code in __init__.py beyond the docstring.
    AVOID: Do NOT create any circular imports by re-exporting from __init__.py at this stage.
  </action>
  <verify>python -c "import pathlib; dirs = list(pathlib.Path('app').rglob('__init__.py')); assert len(dirs) >= 20, f'Only {len(dirs)} packages'; print(f'{len(dirs)} packages created')"</verify>
  <done>All directories exist with __init__.py files containing docstrings. At least 20 packages under app/.</done>
</task>

<task type="auto">
  <name>Configure ruff, mypy, and project files</name>
  <files>pyproject.toml, .gitignore, .env.example</files>
  <action>
    Append to pyproject.toml the tool configurations:

    [tool.ruff]
    target-version = "py312"
    line-length = 120

    [tool.ruff.lint]
    select = ["E", "W", "F", "I", "N", "UP", "B", "S", "A", "C4", "DTZ", "T20", "RET", "SIM", "TCH", "ARG", "PTH", "RUF"]

    [tool.ruff.lint.per-file-ignores]
    "tests/**" = ["S101"]

    [tool.mypy]
    python_version = "3.12"
    strict = true
    warn_return_any = true
    warn_unused_configs = true
    plugins = ["pydantic.mypy"]

    [tool.mypy.pydantic-mypy]
    init_forbid_extra = true
    init_typed = true
    warn_required_dynamic_aliases = true

    [tool.pytest.ini_options]
    asyncio_mode = "auto"
    testpaths = ["tests"]

    Create .gitignore with Python defaults (*.pyc, __pycache__, .venv, .env, dist/, .mypy_cache/, .ruff_cache/, .pytest_cache/).

    Create .env.example with placeholder variables:
    - APP_NAME=AI Backend API
    - DEBUG=false
    - OPENAI__API_KEY=sk-your-key-here
    - OPENAI__MODEL=gpt-4o
    - OPENAI__EMBEDDING_MODEL=text-embedding-3-small
    - REDIS__HOST=localhost
    - REDIS__PORT=6379
    - QDRANT__HOST=localhost
    - QDRANT__PORT=6333
    - API_KEY=your-api-key-here
    - LOG_LEVEL=INFO

    AVOID: Do NOT include actual API keys in .env.example — only placeholders.
  </action>
  <verify>grep -q "strict = true" pyproject.toml && grep -q "OPENAI__API_KEY" .env.example && test -f .gitignore && echo "OK"</verify>
  <done>.gitignore, .env.example exist. pyproject.toml contains ruff, mypy, and pytest config sections.</done>
</task>

</tasks>

<verification>
After all tasks, verify:
- [ ] pyproject.toml is valid TOML with all dependencies and tool configs
- [ ] app/ directory tree has all Clean Architecture layers
- [ ] .gitignore and .env.example exist with correct content
- [ ] All __init__.py files have docstrings
</verification>

<success_criteria>
- [ ] Poetry project fully defined in pyproject.toml
- [ ] 20+ __init__.py files creating Clean Architecture packages
- [ ] ruff + mypy + pytest configured
- [ ] .gitignore and .env.example present
</success_criteria>
