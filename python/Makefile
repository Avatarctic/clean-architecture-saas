.PHONY: help dev dev-build dev-down dev-logs dev-clean test ci-test ci-test-full stop clean reset admin format lint

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development commands
dev: ## Start development environment
	docker-compose up -d

dev-build: ## Build and start development environment
	docker-compose up -d --build

dev-down: ## Stop development environment
	docker-compose down

dev-logs: ## Show development logs (follow)
	docker-compose logs -f app

dev-clean: ## Stop and remove development volumes
	docker-compose down -v

# Testing commands
test: ## Run tests in local environment (requires python env)
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-integration: ## Run integration tests only (requires services running)
	pytest tests/integration/ -v

ci-test: ## Run CI tests (docker-compose.ci.yml)
	docker-compose -f docker-compose.ci.yml up --abort-on-container-exit --exit-code-from app

ci-test-full: ## Run CI tests with test profile (includes test runner)
	docker-compose -f docker-compose.ci.yml --profile test up --abort-on-container-exit

ci-test-build: ## Build and run CI tests
	docker-compose -f docker-compose.ci.yml up --build --abort-on-container-exit --exit-code-from app

# Admin tools
admin: ## Start development environment with pgAdmin
	docker-compose --profile admin up -d

admin-down: ## Stop development environment including pgAdmin
	docker-compose --profile admin down

# Utility commands
stop: ## Stop all containers (dev and CI)
	docker-compose down
	docker-compose -f docker-compose.ci.yml down

clean: ## Remove all containers and volumes (dev and CI)
	docker-compose down -v
	docker-compose -f docker-compose.ci.yml down -v
	docker system prune -f

reset: clean dev-build ## Full reset: clean everything and rebuild

# Database commands
db-shell: ## Open PostgreSQL shell in development database
	docker-compose exec db psql -U postgres -d saas_db

db-logs: ## Show database logs
	docker-compose logs -f db

db-reset: ## Reset development database (removes volume and restarts)
	docker-compose down -v db
	docker-compose up -d db
	@echo "Waiting for database to be ready..."
	@sleep 5
	docker-compose up -d app

# Logs
logs: dev-logs ## Alias for dev-logs

logs-redis: ## Show Redis logs
	docker-compose logs -f redis

logs-all: ## Show all service logs
	docker-compose logs -f

# Format and lint
format: ## Format Python code with black and isort
	black src/ tests/
	isort src/ tests/

lint: ## Run linters (ruff, black check, isort check, mypy)
	ruff check src/ tests/
	black --check src/ tests/
	isort --check-only src/ tests/
	mypy --config-file mypy.ini src/

lint-fix: ## Run linters with auto-fix
	ruff check --fix src/ tests/
	black src/ tests/
	isort src/ tests/

# Type checking
typecheck: ## Run mypy type checker
	mypy --config-file mypy.ini src/

# Quick checks
check: ## Run quick health checks
	@echo "Checking services..."
	@curl -s http://localhost:8081/health || echo "App not responding"
	@docker-compose ps

health: ## Check application health endpoint
	@echo "Checking application health..."
	@curl -s http://localhost:8081/health | python -m json.tool || echo "Health check failed"

# Install/Setup
setup: ## Initial setup (copy .env.example to .env if needed)
	@if [ ! -f .env ]; then \
		echo "Creating .env from .env.example..."; \
		cp .env.example .env; \
		echo ".env created. Please update it with your configuration."; \
	else \
		echo ".env already exists."; \
	fi

install: ## Install Python dependencies locally
	pip install -r requirements.txt
	pip install -r requirements.dev.txt

# OpenAPI spec generation
openapi: ## Generate OpenAPI specification files
	python -c "from src.app.wiring import create_app; import json; app = create_app(); print(json.dumps(app.openapi(), indent=2))" > openapi.json
	@echo "Generated openapi.json"

openapi-yaml: ## Generate OpenAPI specification in YAML format
	python -c "from src.app.wiring import create_app; import yaml; app = create_app(); spec = app.openapi(); spec['info']['description'] = 'Multi-tenant SaaS API with RBAC, audit logging, and feature flags'; spec['info']['version'] = '1.0.0'; spec['servers'] = [{'url': 'http://localhost:8080', 'description': 'Local development'}, {'url': 'https://api.example.com', 'description': 'Production'}]; print(yaml.dump(spec, default_flow_style=False, sort_keys=False))" > openapi.yml
	@echo "Generated openapi.yml"

# Watch mode for development
watch: ## Run app in watch mode (auto-reload)
	docker-compose up app

# Shell access
shell: ## Open shell in running app container
	docker-compose exec app /bin/sh

shell-db: db-shell ## Alias for db-shell
