.PHONY: setup install dev test lint format migrate worker up down logs clean help check-env

# Default target
.DEFAULT_GOAL := help

# Colors for terminal output
BLUE := \033[34m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

## check-env: Verify required environment variables are set
check-env:
	@test -f .env || (echo "$(RED)Error: .env file not found. Run 'cp .env.example .env' and configure it.$(RESET)" && exit 1)
	@grep -q "GENERATE_" .env && echo "$(RED)Error: .env contains placeholder values. Generate secure passwords first!$(RESET)" && exit 1 || true

## setup: Initial project setup (venv, deps, pre-commit)
setup:
	@echo "$(BLUE)Creating virtual environment...$(RESET)"
	python3.11 -m venv .venv
	@echo "$(BLUE)Installing dependencies...$(RESET)"
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"
	@echo "$(BLUE)Setting up pre-commit hooks...$(RESET)"
	.venv/bin/pre-commit install
	@echo "$(BLUE)Copying environment template...$(RESET)"
	@test -f .env || cp .env.example .env
	@echo "$(YELLOW)IMPORTANT: Edit .env and replace all GENERATE_* placeholders with secure values!$(RESET)"
	@echo "$(YELLOW)Generate secrets with: openssl rand -hex 32$(RESET)"
	@echo "$(GREEN)Setup complete! Run 'source .venv/bin/activate' to activate the virtual environment.$(RESET)"

## install: Install dependencies only
install:
	pip install -e ".[dev]"

## up: Start Docker infrastructure
up: check-env
	@echo "$(BLUE)Starting infrastructure...$(RESET)"
	@mkdir -p temporal-config
	@echo "system.forceSearchAttributesCacheRefreshOnRead:" > temporal-config/development.yaml
	@echo "  - value: true" >> temporal-config/development.yaml
	docker compose up -d
	@echo "$(GREEN)Infrastructure started. Waiting for services to be healthy...$(RESET)"
	@sleep 5
	@echo "$(GREEN)Services ready (localhost only):$(RESET)"
	@echo "  - PostgreSQL: 127.0.0.1:5432"
	@echo "  - Redis:      127.0.0.1:6379"
	@echo "  - Temporal:   127.0.0.1:7233"

## down: Stop Docker infrastructure
down:
	docker compose down

## dev: Start API server in development mode (localhost only)
dev: check-env
	@echo "$(BLUE)Starting API server on 127.0.0.1:8000...$(RESET)"
	uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000


## test: Run tests with coverage
test:
	@echo "$(BLUE)Running tests...$(RESET)"
	pytest tests/ -v --cov=src --cov-report=term-missing

## test-fast: Run tests without coverage (faster)
test-fast:
	pytest tests/ -v -x

## lint: Run linting checks
lint:
	@echo "$(BLUE)Running ruff check...$(RESET)"
	ruff check src/ tests/
	@echo "$(BLUE)Running mypy...$(RESET)"
	mypy src/

## format: Format code with ruff
format:
	@echo "$(BLUE)Formatting code...$(RESET)"
	ruff format src/ tests/
	ruff check --fix src/ tests/

## migrate: Run database migrations
migrate: check-env
	@echo "$(BLUE)Running migrations...$(RESET)"
	alembic upgrade head

## migrate-new: Create a new migration
migrate-new: check-env
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

## logs: Tail all Docker logs
logs:
	docker compose logs -f

## clean: Stop containers and remove volumes
clean:
	@echo "$(YELLOW)Stopping containers and removing volumes...$(RESET)"
	docker compose down -v
	rm -rf temporal-config/
	@echo "$(GREEN)Cleanup complete.$(RESET)"

## shell: Open Python shell with app context
shell:
	python -c "from src.config import settings; print('Settings loaded')" && python

## db-shell: Open PostgreSQL shell
db-shell:
	docker exec -it controlplane-postgres psql -U $${POSTGRES_USER:-controlplane} -d $${POSTGRES_DB:-controlplane}

## redis-cli: Open Redis CLI
redis-cli:
	docker exec -it controlplane-redis redis-cli -a $${REDIS_PASSWORD}

## help: Show this help message
help:
	@echo "$(BLUE)Document Extraction Control Plane - Development Commands$(RESET)"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "$(YELLOW)Security Note: Run 'make check-env' to verify .env is properly configured.$(RESET)"
	@echo ""
	@echo "Targets:"
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /' | column -t -s ':'
