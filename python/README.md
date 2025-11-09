# Clean Architecture SaaS Template (Python)# Clean Architecture SaaS Template (Python)# Clean Architecture SaaS Template (Python)# Clean Architecture SaaS Template (Python)



A production-ready, scalable template for building B2B SaaS applications using Clean Architecture principles in Python.



Maintained as an Open Source project by Avatarctic™ — https://avatarctic.comA production-ready, scalable template for building B2B SaaS applications using Clean Architecture principles in Python with FastAPI.



## Overview



This repository implements a pragmatic, production-oriented Clean Architecture example for multi-tenant SaaS platforms. It includes common building blocks you need to ship a modern SaaS product: auth, multi-tenancy, feature flags, audit logging, metrics, and more — wired with real infrastructure (PostgreSQL, Redis, email provider) and CI automation.Maintained as an Open Source project by Avatarctic™ — https://avatarctic.comA production-ready, scalable template for building B2B SaaS applications using Clean Architecture principles in Python with FastAPI.Minimal async FastAPI + SQLAlchemy async scaffold following Clean Architecture principles.



## Key Features & Current Implementation Details



- Clean Architecture layering: `src/app/core` (domain + ports), `src/app/services` (use-cases/services), `src/app/infrastructure` (repositories, adapters), and `src/app/composition.py` as the composition root.## Overview

- Web: FastAPI framework for HTTP handlers and async/await support.

- Auth: JWT-based authentication (dual-token system with python-jose).

- Users: Tenant-aware user management with email verification.

- Multi-tenancy: Tenant isolation built into repositories and service layer.This repository implements a pragmatic, production-oriented Clean Architecture example for multi-tenant SaaS platforms. It includes common building blocks you need to ship a modern SaaS product: auth, multi-tenancy, feature flags, audit logging, metrics, and more — wired with real infrastructure (PostgreSQL, Redis, email provider) and CI automation.Maintained as an Open Source project by Avatarctic™ — https://avatarctic.comQuick start

- Permissions (RBAC & role hierarchy): The application implements role-based access control; permissions are enforced at the HTTP layer using middleware.

- Feature flags: Dynamic feature toggles and evaluation APIs.

- Database: PostgreSQL (async SQLAlchemy + asyncpg). Migrations live under `migrations/` and are applied at startup.

- Redis: Caching repositories and short-lived token caches.## Key Features & Current Implementation Details

- Passwords: bcrypt hashing for persisted passwords. The consolidated migration also seeds an initial admin user (see below).

- Audit logging: Audit entries are recorded in the DB (audit logs table).

- Observability: Prometheus metrics and health endpoints are included, plus structured JSON logging.

- Infrastructure: SendGrid for transactional email.- **Clean Architecture layering**: `src/app/domain` (business entities), `src/app/services` (use-cases), `src/app/infrastructure` (repositories, adapters), and `src/app/composition.py` as the composition root.## Overview1. Create virtualenv and install deps:

- CI: GitHub Actions with linting, unit tests with coverage, Docker builds, and integration tests.

- **Web**: FastAPI framework with async/await support and automatic OpenAPI documentation.

## First system user (seeded)

- **Auth**: JWT-based authentication (dual-token: access + refresh) using python-jose.

On first run the consolidated migration includes an idempotent seed that creates a default platform tenant and an initial admin user. Use the following credentials to sign in locally or during initial testing:

- **Users**: Tenant-aware user management with email verification and password reset flows.

```json

{- **Multi-tenancy**: Tenant isolation built into middleware and repositories. Tenant resolution via host slug or JWT claim.This repository implements a pragmatic, production-oriented Clean Architecture example for multi-tenant SaaS platforms. It includes common building blocks you need to ship a modern SaaS product: auth, multi-tenancy, feature flags, audit logging, metrics, and more — wired with real infrastructure (PostgreSQL, Redis, email provider) and CI automation.```bash

	"email": "admin@example.com",

	"password": "SuperAdmin123!"- **Permissions (RBAC & role hierarchy)**: Role-based access control with permissions enforced at the HTTP layer. Pre-fetched permissions cached in Redis (5-minute TTL).

}

```- **Feature flags**: Dynamic feature toggles with context-aware evaluation (percentage rollouts, user targeting, conditions).python -m venv .venv



If you prefer not to keep the raw password in the migration, consider replacing the migration's crypt() call with a precomputed bcrypt hash and committing that change.- **Database**: PostgreSQL with async SQLAlchemy (asyncpg driver). Migrations live under `migrations/` as SQL files, auto-applied on startup.



## Prerequisites- **Redis**: Caching layer for tenants, tokens, permissions. Configurable TTLs for performance optimization.## Key Features & Current Implementation Detailssource .venv/bin/activate



- Python 3.13+ (module is under `python/`)- **Passwords**: bcrypt hashing via passlib for secure password storage.

- Docker and Docker Compose (for full local stack)

- PostgreSQL (recommended via Docker Compose)- **Connection pooling**: Production-ready pool configuration (20 base + 30 overflow = 50 max connections) with query timeouts (PostgreSQL only).pip install -r requirements.txt

- Redis (recommended via Docker Compose)

- **Audit logging**: Comprehensive audit trail with action/resource tracking stored in PostgreSQL.

## Quick start (development)

- **Observability**: Prometheus metrics endpoint, structured JSON logging (structlog), health checks.- Clean Architecture layering: `src/app/domain` (business entities), `src/app/services` (use-cases), `src/app/infrastructure` (repositories, adapters), and `src/app/composition.py` as the composition root.```

1. Clone and enter the Python module folder:

- **Infrastructure**: SendGrid for transactional email (verification, password reset).

```powershell

git clone <your-repo-url>- **CI**: GitHub Actions with linting (ruff, black, isort, flake8, mypy), unit tests with coverage, Docker builds, and integration tests.- Web: FastAPI framework with async/await support and automatic OpenAPI documentation.

cd clean-architecture-saas/python

cp .env.example .env

```

## First system user (seeded)- Auth: JWT-based authentication (dual-token: access + refresh) using python-jose.2. Copy example env and run with Uvicorn:

2. Edit `.env` and set at minimum `JWT_SECRET`, `SENDGRID_API_KEY`, and DB/Redis connection values. New config knobs exposed in the repo include DB connection pool settings (DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_RECYCLE, DB_POOL_PRE_PING) and cache TTLs (TENANT_CACHE_TTL_SECONDS, token lifetimes).



3. Start services with Docker Compose (recommended):

On first run, the consolidated migration includes an idempotent seed that creates a default platform tenant and an initial admin user. Use the following credentials to sign in locally or during initial testing:- Users: Tenant-aware user management with email verification and password reset flows.

```powershell

docker-compose up -d

```

```json- Multi-tenancy: Tenant isolation built into middleware and repositories. Tenant resolution via host slug or JWT claim.```bash

Files in this module expect Postgres and Redis to be reachable at the values defined in `.env`. The repository includes `docker-compose.yml` to bring up Postgres, Redis and the app.

{

4. **Alternative: Local development** (if you have Python installed locally):

	"email": "admin@example.com",- Permissions (RBAC & role hierarchy): Role-based access control with permissions enforced at the HTTP layer. Pre-fetched permissions cached in Redis.cp .env.example .env

```powershell

# Create virtual environment	"password": "SuperAdmin123!"

python -m venv .venv

.venv\Scripts\Activate.ps1  # Windows}- Feature flags: Dynamic feature toggles with context-aware evaluation (percentage rollouts, user targeting, conditions).uvicorn src.app.main:app --reload

# or: source .venv/bin/activate  # Unix/macOS

```

# Install dependencies

pip install -r requirements.txt- Database: PostgreSQL with async SQLAlchemy (asyncpg driver). Migrations live under `migrations/` as SQL files, auto-applied on startup.```



# Run applicationThe migration uses `crypt()` for bcrypt hashing during seed. For production deployments, consider pre-computing the hash.

uvicorn src.app.main:app --reload --port 8080

```- Redis: Caching layer for tenants, tokens, permissions. Configurable TTLs for performance optimization.



The HTTP server defaults to port 8080 (or 8081 when using Docker Compose).## Prerequisites



## Environment & Configuration- Passwords: bcrypt hashing via passlib for secure password storage.3. Run tests:



Configuration is read from environment variables. See `src/app/config.py` for the complete list. Highlights:- Python 3.13+ (async/await support required)



- JWT_SECRET — signing key for access tokens- Docker and Docker Compose (for full local stack)- Connection pooling: Production-ready pool configuration (20 base + 30 overflow = 50 max connections) with query timeouts.

- DB_* — PostgreSQL connection and pool settings

- REDIS_URL — Redis connection string- PostgreSQL 16+ (recommended via Docker Compose)

- SENDGRID_API_KEY / EMAIL_FROM — transactional email settings

- Redis 7+ (recommended via Docker Compose)- Rate limiting: Placeholder structure for implementing rate limiting on authentication endpoints.```bash

## Testing



- Unit tests:

## Quick start (development)- Audit logging: Comprehensive audit trail with action/resource tracking stored in PostgreSQL.pytest

```powershell

pytest tests/unit/ -v

```

1. Clone and enter the Python module folder:- Observability: Prometheus metrics endpoint, structured JSON logging (structlog), health checks.```

- Integration tests (requires running services):



```powershell

# start stack```powershell- Infrastructure: SendGrid for transactional email (verification, password reset).

docker-compose up -d

git clone <your-repo-url>

# run integration tests

pytest tests/integration/ -vcd clean-architecture-saas/python- CI: GitHub Actions with linting (ruff, black, isort, flake8, mypy), unit tests with coverage, Docker builds, and integration tests.Layout

```

cp .env.example .env

- Run all tests with coverage:

```

```powershell

pytest --cov=src --cov-report=term

```

2. Edit `.env` and set at minimum `JWT_SECRET`, `SENDGRID_API_KEY`, and verify DB/Redis connection values. Key configuration includes:## First system user (seeded)```

## Project layout

   - Connection pool settings: `DB_POOL_SIZE` (20), `DB_MAX_OVERFLOW` (30)

```

python/   - Cache TTLs: `TENANT_CACHE_TTL_SECONDS` (3600), token lifetimespython/

├── src/app/

│   ├── domain/              # domain models and business entities   - Background task intervals: `REFRESH_TOKEN_CLEANUP_INTERVAL_SECONDS`

│   ├── services/            # use-cases and services

│   ├── ports/               # interfaces (Repository protocols)On first run, the consolidated migration includes an idempotent seed that creates a default platform tenant and an initial admin user. Use the following credentials to sign in locally or during initial testing:├── src/yourapp/

│   ├── infrastructure/      # concrete implementations (db, redis, http, email)

│   ├── routers/             # FastAPI route handlers3. Start services with Docker Compose (recommended):

│   ├── middleware/          # request middleware

│   ├── composition.py       # dependency wiring│   ├── api/

│   └── main.py              # application entrypoint

├── tests/                   # unit & integration tests```powershell

├── migrations/              # SQL migrations

└── Dockerfiledocker-compose up -d```json│   ├── adapters/

```

```

## API (selected endpoints)

{│   ├── domain/

- POST /api/v1/auth/login — obtain access and refresh tokens

- POST /api/v1/auth/refresh — refresh tokensThis brings up PostgreSQL, Redis, and the FastAPI application. Migrations run automatically on container startup.

- GET  /api/v1/users — list users (protected)

- POST /api/v1/tenants — create tenant (protected)	"email": "admin@example.com",│   ├── services/

- GET  /health — health check

- GET  /metrics — Prometheus metrics4. **Alternative: Local development** without Docker:

- GET  /docs — interactive API documentation (Swagger UI)

	"password": "SuperAdmin123!"│   └── config.py

Refer to `openapi.json`/`openapi.yml` (generate via `python -c "from src.app.wiring import create_app; ...`) or visit `/docs` for the full API specification.

```powershell

## Contributing & Maintainer

# Create virtual environment}├── alembic/

This project is Open Source and maintained by Avatarctic™ — https://avatarctic.com. Contributions, bug reports and pull requests are welcome. Please follow conventional commits and include tests for new behavior.

python -m venv .venv

## License

.venv\Scripts\Activate.ps1  # Windows PowerShell```├── Dockerfile

MIT

# or: source .venv/bin/activate  # Unix/macOS

---

├── docker-compose.yml

Built with care using Clean Architecture principles.

# Install dependencies

pip install -r requirements.txtThe migration uses `crypt()` for bcrypt hashing during seed. For production deployments, consider pre-computing the hash.└── requirements.txt



# Run application```

uvicorn src.app.main:app --reload --port 8080

```## Prerequisites



5. Access the application:CurrentUserMiddleware

   - API: http://localhost:8081 (Docker) or http://localhost:8080 (local)

   - Health: http://localhost:8081/health- Python 3.13+ (async/await support required)---------------------

   - Swagger docs: http://localhost:8081/docs

   - ReDoc: http://localhost:8081/redoc- Docker and Docker Compose (for full local stack)

   - Metrics: http://localhost:8081/metrics

- PostgreSQL 16+ (recommended via Docker Compose)This template centralizes tenant lookup and current-user resolution in a

## Environment & Configuration

- Redis 7+ (recommended via Docker Compose)single middleware, `src/app/middleware/current_user.py`.

Configuration is read from environment variables via Pydantic `BaseSettings`. See `src/app/config.py` for the complete list. Highlights:



- `JWT_SECRET` — Signing key for access tokens (default: "changeme" - **CHANGE IN PRODUCTION**)

- `ACCESS_TOKEN_TTL_SECONDS` — Access token lifetime (default: 900 = 15 minutes)## Quick start (development)- The middleware resolves the tenant (by host slug or token tenant_id),

- `REFRESH_TOKEN_TTL_SECONDS` — Refresh token lifetime (default: 604800 = 7 days)

- `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` — Connection pool configuration (20/30 for production load)	enforces tenant status (for example, prevents requests when a tenant is

- `TENANT_CACHE_TTL_SECONDS` — Tenant cache duration (3600 = 1 hour, longer cache since tenants rarely change)

- `REDIS_URL` — Redis connection string1. Clone and enter the Python module folder:	suspended), and validates bearer tokens.

- `SENDGRID_API_KEY` / `EMAIL_FROM` — Transactional email settings

- `DATABASE_URL` — Optional full database URL override (useful for tests)- On successful validation the middleware attaches two helpful values to



## Testing```powershell	each request: `request.state.tenant` and `request.state.current_user`.



- **Unit tests** (use in-memory SQLite, no external services required):git clone <your-repo-url>- Many route handlers and dependencies in this project expect the



```powershellcd clean-architecture-saas/python	middleware to have run and will read `request.state.current_user` and

pytest tests/unit/ -v

```cp .env.example .env	`request.state.tenant` directly (there are no runtime fallbacks to a



- **Integration tests** (require running PostgreSQL and Redis):```	secondary dependency). Make sure tests that create app instances use



```powershell	`create_app()` or `main._create_minimal_app()` with the middleware

# Start services

docker-compose up -d2. Edit `.env` and set at minimum `JWT_SECRET`, `SENDGRID_API_KEY`, and verify DB/Redis connection values. Key configuration includes:	registered so those attributes are present.



# Run integration tests   - Connection pool settings: `DB_POOL_SIZE` (20), `DB_MAX_OVERFLOW` (30)

pytest tests/integration/ -v

   - Cache TTLs: `TENANT_CACHE_TTL_SECONDS` (3600), token lifetimesIf you need a dependency-based fallback for apps that don't use the

# Or run all tests

pytest -v   - Background task intervals: `REFRESH_TOKEN_CLEANUP_INTERVAL_SECONDS`middleware, prefer using `get_current_user` from `src/app/deps.py`, which

```

will return the middleware-resolved user when present.

- **Coverage report**:

3. Start services with Docker Compose (recommended):

```powershell

pytest --cov=src --cov-report=html --cov-report=term```powershell

```docker-compose up -d

```

- **CI tests** (Docker Compose with isolated test environment):

This brings up PostgreSQL, Redis, and the FastAPI application. Migrations run automatically on container startup.

```powershell

docker-compose -f docker-compose.ci.yml up --abort-on-container-exit4. **Alternative: Local development** without Docker:

```

```powershell

## Makefile Commands# Create virtual environment

python -m venv .venv

The project includes a comprehensive Makefile for common operations:.venv\Scripts\Activate.ps1  # Windows PowerShell

# or: source .venv/bin/activate  # Unix/macOS

```powershell

make help              # Show all available commands# Install dependencies

make dev               # Start development environmentpip install -r requirements.txt

make dev-build         # Build and start development environment

make test              # Run unit tests locally# Run application

make test-unit         # Run unit tests onlyuvicorn src.app.main:app --reload --port 8080

make test-integration  # Run integration tests only```

make ci-test           # Run CI tests in Docker

make lint              # Run all linters (ruff, black, isort, flake8, mypy)5. Access the application:

make lint-fix          # Run linters with auto-fix   - API: http://localhost:8081 (Docker) or http://localhost:8080 (local)

make format            # Format code with black and isort   - Health: http://localhost:8081/health

make admin             # Start with pgAdmin included   - Swagger docs: http://localhost:8081/docs

make db-shell          # Open PostgreSQL shell   - ReDoc: http://localhost:8081/redoc

make logs              # Follow application logs   - Metrics: http://localhost:8081/metrics

make clean             # Remove all containers and volumes

make openapi           # Generate OpenAPI spec (JSON)## Environment & Configuration

make openapi-yaml      # Generate OpenAPI spec (YAML)

```Configuration is read from environment variables via Pydantic `BaseSettings`. See `src/app/config.py` for the complete list. Highlights:



## Project layout- `JWT_SECRET` — Signing key for access tokens (default: "changeme" - **CHANGE IN PRODUCTION**)

- `ACCESS_TOKEN_TTL_SECONDS` — Access token lifetime (default: 900 = 15 minutes)

```- `REFRESH_TOKEN_TTL_SECONDS` — Refresh token lifetime (default: 604800 = 7 days)

python/- `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` — Connection pool configuration (20/30 for production load)

├── src/app/- `TENANT_CACHE_TTL_SECONDS` — Tenant cache duration (3600 = 1 hour, longer cache since tenants rarely change)

│   ├── domain/              # Business entities (User, Tenant, Permission, FeatureFlag, etc.)- `REDIS_URL` — Redis connection string

│   ├── services/            # Business logic / use cases- `SENDGRID_API_KEY` / `EMAIL_FROM` — Transactional email settings

│   ├── ports/               # Interfaces (Repository protocols, Cache, Email)- `DATABASE_URL` — Optional full database URL override (useful for tests)

│   ├── infrastructure/      # Concrete implementations

│   │   ├── repositories/    # Database access (SQLAlchemy async)## Testing

│   │   ├── cache/           # Redis caching implementations

│   │   ├── email/           # SendGrid email adapter- **Unit tests** (use in-memory SQLite, no external services required):

│   │   └── models/          # SQLAlchemy ORM models

│   ├── routers/             # FastAPI route handlers```powershell

│   ├── middleware/          # Request middleware (tenant resolution, metrics)pytest tests/unit/ -v

│   ├── schemas/             # Pydantic request/response models```

│   ├── deps/                # FastAPI dependency injection

│   ├── composition.py       # Dependency wiring / composition root- **Integration tests** (require running PostgreSQL and Redis):

│   ├── config.py            # Environment configuration

│   ├── main.py              # Application entrypoint```powershell

│   └── db.py                # Database engine setup# Start services

├── tests/docker-compose up -d

│   ├── unit/                # Unit tests (isolated, fast)

│   ├── integration/         # Integration tests (require services)# Run integration tests

│   └── fixtures/            # Shared test fixturespytest tests/integration/ -v

├── migrations/              # SQL migration files

├── Dockerfile               # Production Docker image# Or run all tests

├── docker-compose.yml       # Development environmentpytest -v

├── docker-compose.ci.yml    # CI testing environment```

├── requirements.txt         # Python dependencies

├── Makefile                 # Common development commands- **Coverage report**:

├── pyproject.toml           # Tool configurations (black, ruff, isort, mypy)

└── pytest.ini               # Pytest configuration```powershell

```pytest --cov=src --cov-report=html --cov-report=term

```

## API (selected endpoints)

- **CI tests** (Docker Compose with isolated test environment):

**Authentication:**

- `POST /api/v1/auth/login` — Obtain access and refresh tokens```powershell

- `POST /api/v1/auth/refresh` — Refresh access tokendocker-compose -f docker-compose.ci.yml up --abort-on-container-exit

- `POST /api/v1/auth/logout` — Revoke current session```

- `GET  /api/v1/auth/verify-email` — Email verification (GET for links, POST for API)

- `POST /api/v1/auth/resend-verification` — Resend verification email## Makefile Commands



**Users:**The project includes a comprehensive Makefile for common operations:

- `GET  /api/v1/users` — List users (protected)

- `POST /api/v1/users` — Create user (protected)```powershell

- `GET  /api/v1/users/me` — Get current user profilemake help              # Show all available commands

- `GET  /api/v1/users/{id}` — Get user by IDmake dev               # Start development environment

- `PUT  /api/v1/users/{id}` — Update usermake dev-build         # Build and start development environment

- `DELETE /api/v1/users/{id}` — Delete usermake test              # Run unit tests locally

- `GET  /api/v1/users/{id}/sessions` — List user sessionsmake test-unit         # Run unit tests only

- `POST /api/v1/users/{id}/password` — Change passwordmake test-integration  # Run integration tests only

- `PATCH /api/v1/users/{id}/email` — Update email (sends verification)make ci-test           # Run CI tests in Docker

make lint              # Run all linters (ruff, black, isort, flake8, mypy)

**Tenants:**make lint-fix          # Run linters with auto-fix

- `GET  /api/v1/tenants` — List tenants (protected)make format            # Format code with black and isort

- `POST /api/v1/tenants` — Create tenant (protected)make admin             # Start with pgAdmin included

- `GET  /api/v1/tenants/{id}` — Get tenant by IDmake db-shell          # Open PostgreSQL shell

- `PUT  /api/v1/tenants/{id}` — Update tenantmake logs              # Follow application logs

- `POST /api/v1/tenants/{id}/suspend` — Suspend tenantmake clean             # Remove all containers and volumes

- `POST /api/v1/tenants/{id}/activate` — Activate tenantmake openapi           # Generate OpenAPI spec (JSON)

- `POST /api/v1/tenants/{id}/cancel` — Cancel tenantmake openapi-yaml      # Generate OpenAPI spec (YAML)

```

**Permissions:**

- `GET  /api/v1/permissions` — Get available permissions## Project layout

- `GET  /api/v1/permissions/roles/{role}` — Get role permissions

- `PUT  /api/v1/permissions/roles/{role}` — Set role permissions (bulk)```

- `POST /api/v1/permissions/roles/{role}/permissions` — Add permission to rolepython/

- `DELETE /api/v1/permissions/roles/{role}/permissions/{permission}` — Remove permission├── src/app/

│   ├── domain/              # Business entities (User, Tenant, Permission, FeatureFlag, etc.)

**Feature Flags:**│   ├── services/            # Business logic / use cases

- `GET  /api/v1/features` — List feature flags│   ├── ports/               # Interfaces (Repository protocols, Cache, Email)

- `POST /api/v1/features` — Create feature flag│   ├── infrastructure/      # Concrete implementations

- `POST /api/v1/features/evaluate` — Evaluate feature for context│   │   ├── repositories/    # Database access (SQLAlchemy async)

- `PUT  /api/v1/features/{id}` — Update feature flag│   │   ├── cache/           # Redis caching implementations

- `DELETE /api/v1/features/{id}` — Delete feature flag│   │   ├── email/           # SendGrid email adapter

│   │   └── models/          # SQLAlchemy ORM models

**Audit:**│   ├── routers/             # FastAPI route handlers

- `GET  /api/v1/audit/logs` — List audit events (protected)│   ├── middleware/          # Request middleware (tenant resolution, metrics)

│   ├── schemas/             # Pydantic request/response models

**System:**│   ├── deps/                # FastAPI dependency injection

- `GET  /health` — Health check│   ├── composition.py       # Dependency wiring / composition root

- `GET  /metrics` — Prometheus metrics│   ├── config.py            # Environment configuration

│   ├── main.py              # Application entrypoint

Refer to `openapi.json`/`openapi.yml` (generated via `make openapi`) and the interactive docs at `/docs` for the complete API specification.│   └── db.py                # Database engine setup

├── tests/

## Architecture Notes│   ├── unit/                # Unit tests (isolated, fast)

│   ├── integration/         # Integration tests (require services)

### CurrentUserMiddleware│   └── fixtures/            # Shared test fixtures

├── migrations/              # SQL migration files

The template centralizes tenant lookup and current-user resolution in `src/app/middleware/current_user.py`:├── Dockerfile               # Production Docker image

├── docker-compose.yml       # Development environment

- Resolves tenant by host slug (e.g., `acme.example.com` → `acme`) or JWT `tenant_id` claim├── docker-compose.ci.yml    # CI testing environment

- Enforces tenant status (rejects requests when tenant is suspended)├── requirements.txt         # Python dependencies

- Validates JWT bearer tokens and caches them in Redis├── Makefile                 # Common development commands

- Pre-fetches user permissions and caches them (5-minute TTL)├── pyproject.toml           # Tool configurations (black, ruff, isort, mypy)

- Attaches `request.state.tenant`, `request.state.current_user`, and `request.state.user_permissions` to each request└── pytest.ini               # Pytest configuration

```

Route handlers can access these values directly. Tests must use `create_app()` to ensure middleware is registered, or use `mock_request_state()` helper for unit tests.

## API (selected endpoints)

### Repository Pattern

Authentication:

All database access goes through repository interfaces defined in `src/app/ports/repositories.py`. Use the factory function:- `POST /api/v1/auth/login` — Obtain access and refresh tokens

- `POST /api/v1/auth/refresh` — Refresh access token

```python- `POST /api/v1/auth/logout` — Revoke current session

from src.app.infrastructure.repositories import get_repositories- `GET  /api/v1/auth/verify-email` — Email verification (GET for links, POST for API)

- `POST /api/v1/auth/resend-verification` — Resend verification email

repos = get_repositories(session, cache)  # Returns dict with all repos

user = await repos["users"].get_by_email(email)Users:

```- `GET  /api/v1/users` — List users (protected)

- `POST /api/v1/users` — Create user (protected)

Repositories are automatically decorated with caching when a cache client is provided.- `GET  /api/v1/users/me` — Get current user profile

- `GET  /api/v1/users/{id}` — Get user by ID

### Performance Optimizations- `PUT  /api/v1/users/{id}` — Update user

- `DELETE /api/v1/users/{id}` — Delete user

Recent optimizations implemented:- `GET  /api/v1/users/{id}/sessions` — List user sessions

1. **Bulk operations** - Eliminated N+1 queries in permission assignment (20 queries → 3)- `POST /api/v1/users/{id}/password` — Change password

2. **Removed redundant lookups** - Middleware uses JWT claims instead of extra DB queries (50% reduction)- `PATCH /api/v1/users/{id}/email` — Update email (sends verification)

3. **Cache fallback** - Token validation checks blacklist DB before rejecting on cache miss

4. **Increased connection pool** - 50 max connections (20 base + 30 overflow) for production loadTenants:

5. **Extended cache TTLs** - Tenant cache increased to 1 hour (12x reduction in misses)- `GET  /api/v1/tenants` — List tenants (protected)

6. **Query timeouts** - 30-second timeout prevents runaway queries (PostgreSQL only)- `POST /api/v1/tenants` — Create tenant (protected)

- `GET  /api/v1/tenants/{id}` — Get tenant by ID

## Contributing & Maintainer- `PUT  /api/v1/tenants/{id}` — Update tenant

- `POST /api/v1/tenants/{id}/suspend` — Suspend tenant

This project is Open Source and maintained by Avatarctic™ — https://avatarctic.com. Contributions, bug reports and pull requests are welcome. Please follow conventional commits and include tests for new behavior.- `POST /api/v1/tenants/{id}/activate` — Activate tenant

- `POST /api/v1/tenants/{id}/cancel` — Cancel tenant

## License

Permissions:

MIT- `GET  /api/v1/permissions` — Get available permissions

- `GET  /api/v1/permissions/roles/{role}` — Get role permissions

---- `PUT  /api/v1/permissions/roles/{role}` — Set role permissions (bulk)

- `POST /api/v1/permissions/roles/{role}/permissions` — Add permission to role

Built with care using Clean Architecture principles.- `DELETE /api/v1/permissions/roles/{role}/permissions/{permission}` — Remove permission


Feature Flags:
- `GET  /api/v1/features` — List feature flags
- `POST /api/v1/features` — Create feature flag
- `POST /api/v1/features/evaluate` — Evaluate feature for context
- `PUT  /api/v1/features/{id}` — Update feature flag
- `DELETE /api/v1/features/{id}` — Delete feature flag

Audit:
- `GET  /api/v1/audit/logs` — List audit events (protected)

System:
- `GET  /health` — Health check
- `GET  /metrics` — Prometheus metrics

Refer to `openapi.json`/`openapi.yml` (generated via `make openapi`) and the interactive docs at `/docs` for the complete API specification.

## Architecture Notes

### CurrentUserMiddleware

The template centralizes tenant lookup and current-user resolution in `src/app/middleware/current_user.py`:

- Resolves tenant by host slug (e.g., `acme.example.com` → `acme`) or JWT `tenant_id` claim
- Enforces tenant status (rejects requests when tenant is suspended)
- Validates JWT bearer tokens and caches them in Redis
- Pre-fetches user permissions and caches them (5-minute TTL)
- Attaches `request.state.tenant`, `request.state.current_user`, and `request.state.user_permissions` to each request

Route handlers can access these values directly. Tests must use `create_app()` to ensure middleware is registered, or use `mock_request_state()` helper for unit tests.

### Repository Pattern

All database access goes through repository interfaces defined in `src/app/ports/repositories.py`. Use the factory function:

```python
from src.app.infrastructure.repositories import get_repositories

repos = get_repositories(session, cache)  # Returns dict with all repos
user = await repos["users"].get_by_email(email)
```

Repositories are automatically decorated with caching when a cache client is provided.

### Performance Optimizations

Recent optimizations implemented:
1. **Bulk operations** - Eliminated N+1 queries in permission assignment (20 queries → 3)
2. **Removed redundant lookups** - Middleware uses JWT claims instead of extra DB queries (50% reduction)
3. **Cache fallback** - Token validation checks blacklist DB before rejecting on cache miss
4. **Increased connection pool** - 50 max connections (20 base + 30 overflow) for production load
5. **Extended cache TTLs** - Tenant cache increased to 1 hour (12x reduction in misses)
6. **Query timeouts** - 30-second timeout prevents runaway queries (PostgreSQL only)

## Contributing & Maintainer

This project is Open Source and maintained by Avatarctic™ — https://avatarctic.com. Contributions, bug reports and pull requests are welcome. Please follow conventional commits and include tests for new behavior.

## License

MIT

---

Built with care using Clean Architecture principles.
