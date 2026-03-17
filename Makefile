.PHONY: help up down restart build logs ps shell test lint format clean

# ── Configuration ─────────────────────────────────────────────────────────────
COMPOSE      = docker-compose
API_SERVICE  = api

# Default target
.DEFAULT_GOAL := help

# ── Help ──────────────────────────────────────────────────────────────────────
help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Stack lifecycle ───────────────────────────────────────────────────────────
up:    ## Start the full local stack in detached mode (builds if needed)
	$(COMPOSE) up --build -d
	@echo ""
	@echo "  Stack started!"
	@echo "  API docs:   http://localhost:8000/docs"
	@echo "  Health:     http://localhost:8000/health"
	@echo "  Qdrant UI:  http://localhost:6333/dashboard"
	@echo ""

down:  ## Stop and remove containers (volumes are preserved)
	$(COMPOSE) down

restart:  ## Restart a specific service — usage: make restart s=api
	$(COMPOSE) restart $(s)

build:  ## Rebuild all images from scratch (no cache)
	$(COMPOSE) build --no-cache

# ── Observability ─────────────────────────────────────────────────────────────
logs:  ## Tail logs for all services (or specific: make logs s=api)
	$(COMPOSE) logs -f $(s)

ps:    ## Show status of all services
	$(COMPOSE) ps

# ── Development ───────────────────────────────────────────────────────────────
shell:  ## Open a bash shell in the API container
	$(COMPOSE) exec $(API_SERVICE) /bin/bash

# ── Testing (runs outside Docker via Poetry) ──────────────────────────────────
test:  ## Run the full test suite
	poetry run pytest tests/ -v

test-cov:  ## Run tests with coverage report
	poetry run pytest tests/ -v --cov=app --cov-report=term-missing

# ── Code quality ──────────────────────────────────────────────────────────────
lint:  ## Lint with ruff
	poetry run ruff check app/ tests/

format:  ## Format code with ruff
	poetry run ruff format app/ tests/

typecheck:  ## Run mypy type checking
	poetry run mypy app/

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:  ## Remove containers, volumes, and locally built images
	$(COMPOSE) down --volumes --rmi local
	@echo "  Containers, volumes and local images removed."
