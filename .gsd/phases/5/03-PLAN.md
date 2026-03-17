---
phase: 5
plan: 3
wave: 2
depends_on: [5.1, 5.2]
files_modified:
  - Makefile
  - .dockerignore
autonomous: true

must_haves:
  truths:
    - "Makefile provides make up, make down, make logs, make build, make restart, make clean targets"
    - ".dockerignore excludes non-essential files from build context"
    - "make up starts the full local stack successfully"
---

# Plan 5.3: Makefile, .dockerignore & Developer Experience

## Objective
Polish the local development experience with a `Makefile` providing one-command workflows (`make up`, `make down`, `make logs`, etc.) and a `.dockerignore` to keep the Docker build context lean. After this plan the developer can clone the repo and be running locally in under 5 minutes.

## Context
- @docker-compose.yml — service definitions from Plan 5.2
- @Dockerfile — multi-stage build from Plan 5.1
- @.env.example — environment template from Plan 5.2

## Tasks

<task type="auto">
  <name>Create .dockerignore</name>
  <files>
    .dockerignore
  </files>
  <action>
    Create `.dockerignore` at the project root to exclude everything that does not need to be in the Docker build context. This speeds up `docker build` and prevents accidental secret leakage.

    ```
    # Python
    __pycache__/
    *.py[cod]
    *.pyo
    .pytest_cache/
    .mypy_cache/
    .ruff_cache/
    *.egg-info/
    dist/
    build/

    # Virtual environments
    .venv/
    venv/
    env/

    # Development and CI
    .gsd/
    .agent/
    .gemini/
    tests/
    docs/

    # Environment files (never bake into image)
    .env
    .env.*
    !.env.example

    # Git
    .git/
    .gitignore

    # IDE / OS
    .vscode/
    .idea/
    *.DS_Store
    Thumbs.db

    # Docker files themselves
    docker-compose*.yml
    Dockerfile*
    Makefile

    # Terraform / cloud
    terraform/
    *.tfstate
    *.tfvars
    ```

    Note: `!.env.example` re-includes the example file so it can be used as reference documentation inside the image if needed, but actual `.env` is excluded.
  </action>
  <verify>docker build --target builder -t ai-backend-api:ctx-test . && echo ".dockerignore OK"</verify>
  <done>.dockerignore created; build context does not include .git, .env, .gsd, or __pycache__ directories</done>
</task>

<task type="auto">
  <name>Create Makefile with developer workflow targets</name>
  <files>
    Makefile
  </files>
  <action>
    Create a `Makefile` at the project root with the following targets. Use tabs (not spaces) for recipe lines — this is a hard Make requirement.

    ```makefile
    .PHONY: help up down restart logs build shell test lint format clean

    # ── Configuration ──────────────────────────────────────────
    COMPOSE = docker compose
    API_SERVICE = api

    # ── Help ───────────────────────────────────────────────────
    help:        ## Show this help message
    	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

    # ── Stack lifecycle ─────────────────────────────────────────
    up:          ## Start the full local stack (builds if needed)
    	$(COMPOSE) up --build -d
    	@echo "✓ Stack started. API: http://localhost:8000/docs"

    down:        ## Stop and remove containers
    	$(COMPOSE) down

    restart:     ## Restart a specific service (usage: make restart s=api)
    	$(COMPOSE) restart $(s)

    build:       ## Rebuild all images without cache
    	$(COMPOSE) build --no-cache

    # ── Observability ────────────────────────────────────────────
    logs:        ## Tail logs for all services (or specific: make logs s=api)
    	$(COMPOSE) logs -f $(s)

    ps:          ## Show status of all services
    	$(COMPOSE) ps

    # ── Development ──────────────────────────────────────────────
    shell:       ## Open a shell in the API container
    	$(COMPOSE) exec $(API_SERVICE) /bin/bash

    # ── Testing (runs outside Docker) ────────────────────────────
    test:        ## Run the test suite
    	poetry run pytest tests/ -v

    # ── Code quality ─────────────────────────────────────────────
    lint:        ## Run ruff linter
    	poetry run ruff check app/ tests/

    format:      ## Format code with ruff
    	poetry run ruff format app/ tests/

    # ── Cleanup ──────────────────────────────────────────────────
    clean:       ## Remove containers, volumes, and images
    	$(COMPOSE) down --volumes --rmi local
    	@echo "✓ All containers, volumes, and local images removed"
    ```

    After creating the file, run `make help` to confirm tab formatting is correct (tabs, not spaces, are required).
  </action>
  <verify>make help</verify>
  <done>make help produces formatted output with all targets visible (up, down, logs, build, restart, clean, test, lint, format, shell)</done>
</task>

## Success Criteria
- [ ] `.dockerignore` created; `.git` and `.env` excluded from build context
- [ ] `Makefile` created; `make help` shows all targets without errors
- [ ] `make up` can start the full local stack end-to-end
