.PHONY: setup install dev test lint format migrate worker up down logs clean help

# Default target
.DEFAULT_GOAL := help

# Colors for terminal output
BLUE := \033[34m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

## setup: Initial project setup (venv, deps, pre-commit)
setup:
	@echo "$(BLUE)Creating virtual environment...$(RESET)"
	python3.11 -m venv .venv
	@echo "$(BLUE)Installing dependencies...$(RESET)"
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev,ml]"
	@echo "$(BLUE)Setting up pre-commit hooks...$(RESET)"
	.venv/bin/pre-commit install
	@echo "$(BLUE)Copying environment template...$(RESET)"
	@test -f .env || cp .env.example .env
	@echo "$(GREEN)Setup complete! Run 'source .venv/bin/activate' to activate the virtual environment.$(RESET)"

## install: Install dependencies only
install:
	pip install -e ".[dev,ml]"

## up: Start Docker infrastructure
up:
	@echo "$(BLUE)Starting infrastructure...$(RESET)"
	@mkdir -p temporal-config
	@echo "system.forceSearchAttributesCacheRefreshOnRead:" > temporal-config/development.yaml
	@echo "  - value: true" >> temporal-config/development.yaml
	docker-compose up -d
	@echo "$(GREEN)Infrastructure started. Waiting for services to be healthy...$(RESET)"
	@sleep 10
	@echo "$(GREEN)Services ready:$(RESET)"
	@echo "  - PostgreSQL:   localhost:5432"
	@echo "  - TimescaleDB:  localhost:5433"
	@echo "  - Redis:        localhost:6379"
	@echo "  - Kafka:        localhost:9092"
	@echo "  - Temporal:     localhost:7233"
	@echo "  - Temporal UI:  http://localhost:8080"
	@echo "  - Kafka UI:     http://localhost:8081"

## down: Stop Docker infrastructure
down:
	docker-compose down

## dev: Start API server in development mode
dev:
	@echo "$(BLUE)Starting API server...$(RESET)"
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

## worker: Start Temporal worker
worker:
	@echo "$(BLUE)Starting Temporal worker...$(RESET)"
	python -m src.workflows.worker

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
migrate:
	@echo "$(BLUE)Running migrations...$(RESET)"
	alembic upgrade head

## migrate-new: Create a new migration
migrate-new:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

## logs: Tail Docker logs
logs:
	docker-compose logs -f

## logs-api: Tail API logs only
logs-api:
	docker-compose logs -f postgres redis kafka temporal

## clean: Stop containers and remove volumes
clean:
	@echo "$(YELLOW)Stopping containers and removing volumes...$(RESET)"
	docker-compose down -v
	rm -rf temporal-config/
	@echo "$(GREEN)Cleanup complete.$(RESET)"

## shell: Open Python shell with app context
shell:
	python -c "from src.core.config import settings; print('Settings loaded')" && python

## db-shell: Open PostgreSQL shell
db-shell:
	docker exec -it controlplane-postgres psql -U controlplane -d controlplane

## redis-cli: Open Redis CLI
redis-cli:
	docker exec -it controlplane-redis redis-cli

## help: Show this help message
help:
	@echo "$(BLUE)Document Extraction Control Plane - Development Commands$(RESET)"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /' | column -t -s ':'
