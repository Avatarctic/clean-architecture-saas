# Clean Architecture SaaS Template (Go)

A production-ready, scalable template for building B2B SaaS applications using Clean Architecture principles in Go.

Maintained as an Open Source project by Avatarctic™ — https://avatarctic.com

## Overview

This repository implements a pragmatic, production-oriented Clean Architecture example for multi-tenant SaaS platforms. It includes common building blocks you need to ship a modern SaaS product: auth, multi-tenancy, feature flags, audit logging, metrics, and more — wired with real infrastructure (PostgreSQL, Redis, email provider) and CI automation.

## Key Features & Current Implementation Details

- Clean Architecture layering: `internal/core` (domain + ports), `internal/application` (use-cases/services), `internal/infrastructure` (repositories, adapters), and `cmd/server` as the composition root.
- Web: Echo framework for HTTP handlers and middleware.
- Auth: JWT-based authentication (github.com/golang-jwt/jwt/v5).
- Users: Tenant-aware user management.
- Multi-tenancy: Tenant isolation built into repositories and service layer.
- Permissions (RBAC & role hierarchy): The application implements role-based access control with a small role hierarchy (super_admin, admin, member, guest); permissions are enforced at the HTTP layer using middleware. 
- Feature flags: Dynamic feature toggles and evaluation APIs.
- Database: PostgreSQL (SQL access via sqlx). Migrations live under `migrations/` and are applied with the included migration tooling.
- Redis: caching repositories and short-lived token caches.
- Passwords: bcrypt hashing for persisted passwords. The consolidated migration also seeds an initial admin user (see below).
- Rate limiting: A configurable rate limiter protects public and tenant-scoped endpoints. It can be configured per-tenant or globally.
- Audit logging: Audit entries are recorded in the DB (audit logs table).
- Observability: Prometheus metrics and health endpoints are included, plus structured JSON logging.
- Infrastructure: SendGrid for transactional email.
- CI: GitHub Actions with integration test job that uses Docker Compose and a TEST_SERVER_URL-driven integration harness.

## First system user (seeded)

On first run the consolidated migration includes an idempotent seed that creates a default platform tenant and an initial admin user. Use the following credentials to sign in locally or during initial testing:

```json
{
	"email": "admin@example.com",
	"password": "SuperAdmin123!"
}
```

If you prefer not to keep the raw password in the migration, consider replacing the migration's crypt() call with a precomputed bcrypt hash and committing that change.

## Prerequisites

- Go 1.21+ (module is under `go/`)
- Docker and Docker Compose (for full local stack)
- PostgreSQL (recommended via Docker Compose)
- Redis (recommended via Docker Compose)

## Quick start (development)

1. Clone and enter the Go module folder:

```powershell
git clone <your-repo-url>
cd clean-architecture-saas/go
cp .env.example .env
```

2. Edit `.env` and set at minimum `JWT_SECRET` and DB/Redis connection values. New config knobs exposed in the repo include DB connection pool settings (DB_MAX_OPEN_CONNS, DB_MAX_IDLE_CONNS, DB_CONN_MAX_LIFETIME, DB_CONN_MAX_IDLE_TIME) and Redis pool/timeouts (REDIS_POOL_SIZE, REDIS_MIN_IDLE_CONNS, REDIS_DIAL_TIMEOUT, etc.).

3. Start services with Docker Compose (recommended):

```powershell
docker-compose -f docker-compose.yml up -d
```

Files in this module expect Postgres and Redis to be reachable at the values defined in `.env`. The repository includes `docker-compose.yml` to bring up Postgres, Redis and the app.

4. Apply DB migrations (from the `go/` folder):

```powershell
# download deps
go mod download

# run migrations (uses the project's migration tool)
go run cmd/migrate/main.go up
```

5. Run the application locally:

```powershell
go run cmd/server/main.go
```

The HTTP server defaults to port 8080 unless TLS is configured via `TLS_CERT_FILE` / `TLS_KEY_FILE` in the environment.

## Environment & Configuration

Configuration is read from environment variables. See `configs/config.go` for the complete list. Highlights:

- JWT_SECRET — signing key for access tokens
- DB_* — PostgreSQL connection and pool settings
- REDIS_* — Redis connection and pool/timeouts
- SMTP_* / SENDGRID_* — transactional email settings

## Testing

- Unit tests:

```powershell
go test ./... -run Test -v
```

- Integration tests (the integration job in CI uses Docker Compose and exposes a TEST_SERVER_URL; locally you can point the integration tests at a running server):

```powershell
# start stack
docker-compose -f docker-compose.yml up -d

# run integration tests (ensure TEST_SERVER_URL is set if needed)
go test ./test/integration -v
```

## Project layout

```
go/
├── cmd/                    # application entrypoints (server, migrate)
├── configs/                # environment-driven configuration
├── internal/
│   ├── application/        # use-cases and services
│   ├── core/               # domain models and ports (interfaces)
│   └── infrastructure/     # concrete implementations (db, redis, http, email)
├── migrations/             # consolidated SQL migrations
├── test/                   # unit & integration tests
└── Dockerfile
```

## API (selected endpoints)

- POST /api/v1/auth/login — obtain access and refresh tokens
- POST /api/v1/auth/refresh — refresh tokens
- GET  /api/v1/users — list users (protected)
- POST /api/v1/tenants — create tenant (protected)
- GET  /health — health check
- GET  /metrics — Prometheus metrics

Refer to `openapi.yml` and to the handlers in `internal/infrastructure/http` for the full list and request/response shapes.

## Contributing & Maintainer

This project is Open Source and maintained by Avatarctic™ — https://avatarctic.com. Contributions, bug reports and pull requests are welcome. Please follow conventional commits and include tests for new behavior.

## License

MIT

---

Built with care using Clean Architecture principles.
