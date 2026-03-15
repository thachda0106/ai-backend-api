---
phase: 2
plan: 2
wave: 1
depends_on: []
files_modified:
  - app/infrastructure/token/__init__.py
  - app/infrastructure/token/tiktoken_service.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "TiktokenService implements TokenService ABC from domain"
    - "Token counting uses tiktoken for accurate model-specific counts"
    - "Cost estimation uses per-model pricing tables"
    - "Truncation preserves complete words/tokens"
---

# Plan 2.2: Token Counting Service (tiktoken)

## Objective
Implement the concrete `TokenService` using tiktoken for accurate token counting, cost estimation, and text truncation. This service is needed by the chunking pipeline and the RAG chat use case.

## Context
- @app/domain/services/token_service.py — TokenService ABC (count_tokens, estimate_cost, truncate_to_token_limit)
- @app/core/config/settings.py — OpenAISettings.model, OpenAISettings.embedding_model

## Tasks

<task type="auto">
  <name>Create infrastructure token package</name>
  <files>app/infrastructure/token/__init__.py</files>
  <action>
    Create the `__init__.py` for the token package with docstring.
  </action>
  <verify>python -m poetry run python -c "import app.infrastructure.token; print('OK')"</verify>
  <done>Package importable</done>
</task>

<task type="auto">
  <name>Implement TiktokenService</name>
  <files>app/infrastructure/token/tiktoken_service.py</files>
  <action>
    Implement `TiktokenService(TokenService)`:
    
    1. `count_tokens(text, model)`:
       - Use `tiktoken.encoding_for_model(model)` to get encoder
       - Return `len(encoder.encode(text))`
       - Cache encoders by model name (dict or lru_cache)
    
    2. `estimate_cost(prompt_tokens, completion_tokens, model)`:
       - Define a pricing dict for common models:
         - gpt-4o: $2.50 / $10 per 1M tokens (input/output)
         - gpt-4o-mini: $0.15 / $0.60 per 1M tokens
         - text-embedding-3-small: $0.02 per 1M tokens
         - text-embedding-3-large: $0.13 per 1M tokens
       - Return estimated cost in USD
       - Return 0.0 for unknown models (don't raise)
    
    3. `truncate_to_token_limit(text, max_tokens, model)`:
       - Encode text, slice to max_tokens, decode back
       - Ensure clean decode (no partial UTF-8)
    
    Handle `KeyError` from tiktoken gracefully — fall back to `cl100k_base` encoding for unknown models.
  </action>
  <verify>python -m poetry run python -c "from app.infrastructure.token.tiktoken_service import TiktokenService; svc = TiktokenService(); count = svc.count_tokens('Hello World', 'gpt-4o'); print(f'Token count: {count}'); cost = svc.estimate_cost(100, 50, 'gpt-4o'); print(f'Cost: ${cost:.6f}'); trunc = svc.truncate_to_token_limit('Hello World this is a long text', 3, 'gpt-4o'); print(f'Truncated: {trunc}'); print('OK')"</verify>
  <done>TiktokenService counts tokens accurately, estimates costs, and truncates text</done>
</task>

## Success Criteria
- [ ] `TiktokenService` implements all 3 methods of `TokenService` ABC
- [ ] Token counting uses model-specific encoders via tiktoken
- [ ] Cost estimation has pricing for gpt-4o, gpt-4o-mini, embedding models
- [ ] Truncation returns valid text within token limits
