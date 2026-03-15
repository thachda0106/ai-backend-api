---
phase: 1
plan: 2
wave: 1
depends_on: []
files_modified:
  - app/core/config/settings.py
  - app/core/logging/setup.py
  - app/core/logging/context.py
  - app/core/security/api_key.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Settings class loads from .env with nested pydantic-settings"
    - "Structured logging is configured with structlog"
    - "API key security stub exists"
  artifacts:
    - "app/core/config/settings.py exists with Settings class"
    - "app/core/logging/setup.py exists with configure_logging function"
---

# Plan 1.2: Core Configuration & Logging

<objective>
Implement the core configuration system using pydantic-settings v2 with nested models, structured logging with structlog, and API key authentication stub.

Purpose: Every layer depends on configuration and logging. This must be in place before domain or infrastructure code.
Output: Working Settings class, structured logging, and security foundation.
</objective>

<context>
Load for context:
- .gsd/SPEC.md
- .gsd/phases/1/RESEARCH.md (§3 pydantic-settings Configuration)
- app/core/config/__init__.py (exists from Plan 1.1)
- app/core/logging/__init__.py (exists from Plan 1.1)
- .env.example
</context>

<tasks>

<task type="auto">
  <name>Create Settings class with nested models</name>
  <files>app/core/config/settings.py</files>
  <action>
    Create the Settings class using pydantic-settings v2:

    1. Create sub-models (inherit from BaseModel, NOT BaseSettings):
       - OpenAISettings: api_key (SecretStr, required), model (str, default "gpt-4o"), embedding_model (str, default "text-embedding-3-small"), max_retries (int, default 3), embedding_dimensions (int, default 1536)
       - RedisSettings: host (str, default "localhost"), port (int, default 6379), db (int, default 0), password (SecretStr | None, default None)
       - QdrantSettings: host (str, default "localhost"), port (int, default 6333), grpc_port (int, default 6334), collection_name (str, default "documents"), prefer_grpc (bool, default True)
       - ChunkingSettings: chunk_size (int, default 512), chunk_overlap (int, default 50), separator (str, default "\n")
       - RateLimitSettings: requests_per_minute (int, default 60), burst_size (int, default 10)

    2. Create main Settings class (inherit from BaseSettings):
       - model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", env_ignore_empty=True, case_sensitive=False)
       - app_name: str = "AI Backend API"
       - debug: bool = False
       - log_level: str = "INFO"
       - api_key: SecretStr (required — for authenticating API clients)
       - openai: OpenAISettings (required — no default, forces explicit config)
       - redis: RedisSettings = RedisSettings()
       - qdrant: QdrantSettings = QdrantSettings()
       - chunking: ChunkingSettings = ChunkingSettings()
       - rate_limit: RateLimitSettings = RateLimitSettings()

    3. Create a get_settings() function with @lru_cache for singleton access.

    Use full type annotations. Import SecretStr from pydantic.

    AVOID: Do NOT inherit sub-models from BaseSettings — only the root Settings class.
    AVOID: Do NOT use os.environ anywhere — all config goes through Settings.
  </action>
  <verify>python -c "from app.core.config.settings import Settings; print('Settings class imported OK')" 2>&1 || echo "Import check - will work after poetry install"</verify>
  <done>Settings class with 5 nested sub-models, all fields typed, get_settings() singleton function</done>
</task>

<task type="auto">
  <name>Configure structured logging with structlog</name>
  <files>app/core/logging/setup.py, app/core/logging/context.py</files>
  <action>
    Create app/core/logging/setup.py:

    1. configure_logging(log_level: str, debug: bool) function that:
       - Sets up structlog with JSON output for production, console output for debug
       - Configures processors: add_log_level, TimeStamper(fmt="iso"), StackInfoRenderer, format_exc_info
       - Sets stdlib logging integration
       - Returns the configured logger

    2. get_logger(name: str) function that returns a bound structlog logger

    Create app/core/logging/context.py:

    1. RequestContext dataclass with: request_id (str), method (str), path (str), user_id (str | None)
    2. bind_request_context(context: RequestContext) function to bind context vars to structlog
    3. Correlation ID generation using uuid4

    AVOID: Do NOT use print() anywhere — always use structlog.
    AVOID: Do NOT configure logging at import time — only when configure_logging() is called.
  </action>
  <verify>python -c "from app.core.logging.setup import configure_logging, get_logger; print('Logging module imported OK')" 2>&1 || echo "Import check"</verify>
  <done>Structured logging configured with JSON/console output, request context binding, correlation IDs</done>
</task>

<task type="auto">
  <name>Create API key authentication stub</name>
  <files>app/core/security/api_key.py</files>
  <action>
    Create app/core/security/api_key.py:

    1. APIKeyHeader class that extends FastAPI's security scheme
    2. verify_api_key(api_key: str, expected_key: SecretStr) -> bool function
    3. A FastAPI dependency function get_api_key() that:
       - Extracts API key from X-API-Key header
       - Validates against settings
       - Raises HTTPException(401) on failure
       - Returns the validated key string

    Import from fastapi.security import APIKeyHeader as FastAPIKeyHeader
    Use SecretStr.get_secret_value() for comparison
    Use hmac.compare_digest for timing-safe comparison

    AVOID: Do NOT implement full OAuth/JWT — this is a simple API key guard.
    AVOID: Do NOT hard-code any keys — always reference Settings.
  </action>
  <verify>python -c "from app.core.security.api_key import verify_api_key; print('Security module imported OK')" 2>&1 || echo "Import check"</verify>
  <done>API key authentication dependency ready for FastAPI router integration</done>
</task>

</tasks>

<verification>
After all tasks, verify:
- [ ] Settings class loads nested config with env_nested_delimiter="__"
- [ ] Structured logging outputs JSON in production mode
- [ ] API key authentication dependency is a valid FastAPI Depends function
</verification>

<success_criteria>
- [ ] Settings class with 5 nested sub-models and get_settings() singleton
- [ ] Structured logging with JSON/console modes and request context
- [ ] API key security dependency with timing-safe comparison
</success_criteria>
