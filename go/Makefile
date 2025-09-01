.PHONY: help setup build run test test-unit test-integration lint clean docker-build docker-up docker-down migrate-up migrate-down

# Variables
APP_NAME := clean-architecture-saas
DOCKER_IMAGE := $(APP_NAME):latest
MIGRATION_PATH := ./migrations

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Setup the development environment
	@echo "🚀 Setting up development environment..."
	@if [ ! -f .env ]; then cp .env.example .env; echo "📝 Created .env file"; fi
	@go mod download
	@go mod tidy
	@echo "✅ Setup complete!"

build: ## Build the application
	@echo "🔨 Building application..."
	@go build -o bin/server ./cmd/server
	@echo "✅ Build complete!"

run: ## Run the application locally
	@echo "🚀 Starting application..."
	@go run ./cmd/server

test: ## Run all tests
	@echo "🧪 Running all tests..."
	@go test -v -race -coverprofile=coverage.out ./...

test-unit: ## Run unit tests only
	@echo "🧪 Running unit tests..."
	@go test -v ./test/unit/...

test-integration: ## Run integration tests only
	@echo "🧪 Running integration tests..."
	@go test -v ./test/integration/...

test-coverage: test ## Run tests and show coverage
	@echo "📊 Test coverage report:"
	@go tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report generated: coverage.html"

coverage-ci: ## Run tests and generate coverage profile compatible with CI
	@echo "📊 Generating coverage profile..."
	@mkdir -p coverage
	@go test ./... -v -covermode=atomic -coverprofile=coverage/cover.out
	@go tool cover -func=coverage/cover.out | sed -n '1,200p'

lint: ## Run linter
	@echo "🔍 Running linter..."
	@golangci-lint run --timeout=5m

lint-fix: ## Run linter and fix issues
	@echo "🔧 Running linter with auto-fix..."
	@golangci-lint run --fix --timeout=5m

clean: ## Clean build artifacts
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf bin/
	@rm -rf tmp/
	@rm -f coverage.out coverage.html
	@echo "✅ Clean complete!"

# Docker commands
docker-build: ## Build Docker image
	@echo "🐳 Building Docker image..."
	@docker build -t $(DOCKER_IMAGE) .

docker-up: ## Start development environment with Docker Compose
	@echo "🐳 Starting development environment..."
	@docker-compose up -d

docker-down: ## Stop development environment
	@echo "🐳 Stopping development environment..."
	@docker-compose down

docker-logs: ## Show application logs
	@docker-compose logs -f app

# Database commands
migrate-up: ## Run database migrations up
	@echo "📊 Running database migrations..."
	@migrate -path $(MIGRATION_PATH) -database "${DATABASE_URL}" up

migrate-down: ## Run database migrations down
	@echo "📊 Rolling back database migrations..."
	@migrate -path $(MIGRATION_PATH) -database "${DATABASE_URL}" down

migrate-create: ## Create a new migration file (usage: make migrate-create NAME=migration_name)
	@if [ -z "$(NAME)" ]; then echo "Usage: make migrate-create NAME=migration_name"; exit 1; fi
	@migrate create -ext sql -dir $(MIGRATION_PATH) -seq $(NAME)

# Development helpers
dev: docker-up ## Start development environment and watch for changes
	@echo "🔄 Starting development mode..."
	@air # Requires air for hot reloading: go install github.com/cosmtrek/air@latest

deps: ## Update dependencies
	@echo "📦 Updating dependencies..."
	@go get -u ./...
	@go mod tidy

security: ## Run security scanner
	@echo "🔒 Running security scanner..."
	@gosec ./...

benchmark: ## Run benchmarks
	@echo "⚡ Running benchmarks..."
	@go test -bench=. -benchmem ./...

# Release commands
release-build: ## Build for multiple platforms
	@echo "📦 Building for multiple platforms..."
	@GOOS=linux GOARCH=amd64 go build -o bin/server-linux-amd64 ./cmd/server
	@GOOS=windows GOARCH=amd64 go build -o bin/server-windows-amd64.exe ./cmd/server
	@GOOS=darwin GOARCH=amd64 go build -o bin/server-darwin-amd64 ./cmd/server
	@GOOS=darwin GOARCH=arm64 go build -o bin/server-darwin-arm64 ./cmd/server
	@echo "✅ Multi-platform build complete!"

install-tools: ## Install development tools
	@echo "🛠 Installing development tools..."
	@go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	@go install github.com/cosmtrek/air@latest
	@go install -tags 'postgres' github.com/golang-migrate/migrate/v4/cmd/migrate@latest
	@echo "✅ Tools installed!"
