import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path for tests
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# CRITICAL: Set up bcrypt shim BEFORE any imports that might trigger passlib
# Passlib tries to read bcrypt.__about__.__version__ and fails if it doesn't exist.
# We create a minimal namespace object to provide the version info.
try:
    import bcrypt as _bcrypt  # noqa: E402 isort: skip
    from types import SimpleNamespace  # isort: skip

    if not hasattr(_bcrypt, "__about__"):
        # Create a simple namespace that passlib can read
        _bcrypt.__about__ = SimpleNamespace(__version__="4.0.1")
    elif not hasattr(_bcrypt.__about__, "__version__"):
        # __about__ exists but missing __version__
        _bcrypt.__about__.__version__ = "4.0.1"
except ImportError:
    pass  # bcrypt not installed, tests will handle appropriately

import asyncio
import os
import tempfile

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

import src.app.infrastructure.db.models as models

Base = models.Base
from src.app.infrastructure.cache.redis_client import InMemoryCache

# Create a temporary sqlite file DB for the test session and set DATABASE_URL before app import
_tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmpfile.close()
from pathlib import Path as _Path

# Use a POSIX-style path in the URL so SQLAlchemy on Windows parses it correctly
posix_path = _Path(_tmpfile.name).as_posix()
# Force the test DATABASE_URL to the temp file so local env vars don't interfere
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{posix_path}"

# CRITICAL: Set DATABASE_URL BEFORE importing app.main or any modules that might
# create DB engines. The session-scoped fixture below will import app.main AFTER
# this point, ensuring the test DB URL is respected.


from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

# Create a single shared engine for tests so create_all and test sessions use the
# same engine instance (avoids platform-specific URL parsing producing slightly
# different engines on Windows).
_TEST_DB_URL = os.environ.get("DATABASE_URL")
# DEBUG: shared test DB URL is set in _TEST_DB_URL
_TEST_ENGINE = _create_async_engine(_TEST_DB_URL, echo=False)


async def _create_tables():
    async with _TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.run(_create_tables())

# Diagnostic: verify that the canonical models module registered the feature_flags table
try:
    import importlib

    models_mod = importlib.import_module("src.app.infrastructure.db.models")

    # If create_all ran against a different metadata this will raise so tests
    # fail loudly during development.
    if "feature_flags" not in models_mod.Base.metadata.tables:
        raise RuntimeError("feature_flags missing from Base.metadata after create_all")
except Exception as _e:
    # Re-raise so test runs fail loudly and we can see the diagnostic output
    print("DEBUG: conftest post-create_all diagnostics failed:", repr(_e))
    raise


import atexit


def _cleanup_tmpfile():
    try:
        os.unlink(_tmpfile.name)
    except Exception:
        pass


atexit.register(_cleanup_tmpfile)


@pytest.fixture(scope="session", autouse=True)
def override_app_db():
    """Create an engine + sessionmaker for tests and override app.get_db to use it.

    Ensure the engine uses the actual temporary file path (Path.as_posix) so the
    sqlite URL is parsed correctly on Windows.
    """
    # Reuse the shared test engine created above so create_all and request
    # sessions share the same underlying DB and connection pool.
    engine = _TEST_ENGINE
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Rebind the app-level db module's engine and AsyncSessionLocal so any
    # code that imported them at module import time will use the shared test engine.
    try:
        import importlib

        db_mod = importlib.import_module("src.app.db")
        # prefer using the public factory so the intent is clear; fall back to
        # manual sessionmaker construction if the helper isn't available.
        db_mod.engine = _TEST_ENGINE
        try:
            # Create and register AsyncSessionLocal via the public helper
            db_mod.create_sessionmaker(_TEST_ENGINE)
            AsyncSessionLocal = db_mod.AsyncSessionLocal
        except Exception:
            # helper missing or failed: construct the sessionmaker directly
            AsyncSessionLocal = sessionmaker(
                _TEST_ENGINE, expire_on_commit=False, class_=AsyncSession
            )
            db_mod.AsyncSessionLocal = AsyncSessionLocal
    except Exception:
        # non-fatal: if the module isn't loaded yet, the later dependency override
        # will ensure the test sessions are used. We intentionally avoid noisy
        # prints here to keep test output clean.
        pass

    async def _override_get_db():
        # yield a session from the shared test AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            yield session

    # override deps.get_db directly (avoid importing src.app.main here so tests can control env before importing app)
    from src.app import deps as app_deps

    # FastAPI routes may have captured the original deps.get_db function object at
    # import time. Save the original and register a dependency override on the
    # app so any route using the original function will be redirected to the
    # test override.
    orig_get_db = app_deps.get_db
    app_deps.get_db = _override_get_db
    try:
        # import app and register the dependency override mapping
        from src.app import main as app_main

        app_main.app.dependency_overrides[orig_get_db] = _override_get_db
        # Ensure tests explicitly use an in-memory cache client by setting
        # the app state value. This avoids relying on dynamic runtime
        # fallbacks inside deps.get_cache_client during tests.
        try:
            app_main.app.state.cache_client = InMemoryCache()
        except Exception:
            # non-fatal if setting the app state fails
            pass
        # Some dependencies get captured on route creation; scan all routes for any
        # dependency callables that point to the original get_db and override them
        # as well. This handles cases where test modules imported `app` before the
        # fixture ran.
        try:
            from fastapi.routing import APIRoute

            for r in list(app_main.app.routes):
                if isinstance(r, APIRoute) and getattr(r, "dependant", None):
                    for dep in getattr(r.dependant, "dependencies", []) or []:
                        callable_obj = getattr(dep, "call", None)
                        if (
                            callable_obj
                            and getattr(callable_obj, "__module__", "") == "src.app.deps"
                            and getattr(callable_obj, "__name__", "") == "get_db"
                        ):
                            app_main.app.dependency_overrides[callable_obj] = _override_get_db
        except Exception:
            # non-critical if route inspection fails; the primary override above helps most cases
            pass
    except Exception:
        # if app wasn't imported by tests yet, ignore; the override will still
        # be useful for code that imports deps.get_db directly.
        pass

    yield

    # teardown: remove dependency override and dispose engine
    try:
        from src.app import main as app_main

        app_main.app.dependency_overrides.pop(orig_get_db, None)
        # Clear the cache client we set earlier to avoid leaking state across test runs
        try:
            if hasattr(app_main.app.state, "cache_client"):
                delattr(app_main.app.state, "cache_client")
        except Exception:
            pass
    except Exception:
        pass
    asyncio.run(engine.dispose())


@pytest.fixture(autouse=True)
async def cleanup_database():
    """Clean up database tables and cache between tests to ensure isolation."""
    yield  # Let the test run first

    # After test completes, clean up all tables
    async with _TEST_ENGINE.begin() as conn:
        # Delete in order to respect foreign key constraints
        await conn.execute(Base.metadata.tables["audit_events"].delete())
        await conn.execute(Base.metadata.tables["blacklisted_tokens"].delete())
        await conn.execute(Base.metadata.tables["refresh_tokens"].delete())
        await conn.execute(Base.metadata.tables["feature_flags"].delete())
        await conn.execute(Base.metadata.tables["permissions"].delete())
        await conn.execute(Base.metadata.tables["roles"].delete())
        await conn.execute(Base.metadata.tables["users"].delete())
        await conn.execute(Base.metadata.tables["tenants"].delete())

    # Clear the cache to prevent test pollution
    # The app may have a cached InMemoryCache instance in app.state.cache_client
    # that's shared across tests. Clear its internal store to ensure isolation.
    try:
        from src.app import main as app_main

        if hasattr(app_main, "app") and hasattr(app_main.app.state, "cache_client"):
            cache = app_main.app.state.cache_client
            if hasattr(cache, "store"):  # InMemoryCache
                async with cache.lock:
                    cache.store.clear()
    except Exception:
        # If cache clearing fails, tests should still pass with their own cache fixture
        pass


# Per-test temporary database URL (function-scoped) and test app fixture
@pytest.fixture
def database_url(tmp_path):
    """Return a sqlite+aiosqlite URL backed by a per-test file in pytest's tmp_path."""
    db_file = tmp_path / "test.db"
    # Use POSIX path so SQLAlchemy parses correctly on Windows
    return f"sqlite+aiosqlite:///{db_file.as_posix()}"


@pytest.fixture
def test_app(database_url, cache):
    """Create a TestClient + engine + AsyncSessionLocal backed by an ephemeral DB.

    Yields (client, engine, AsyncSessionLocal).
    """
    # Lazy import to avoid importing app before tests configure env
    from tests.fixtures.app_factory import create_test_app

    # pass explicit in-memory cache so tests control the cache implementation
    client, engine, AsyncSessionLocal = create_test_app(database_url=database_url, cache=cache)

    try:
        yield client, engine, AsyncSessionLocal
    finally:
        # dispose engine if present; tmp_path cleans up the file
        if engine is not None:
            import asyncio as _asyncio

            try:
                _asyncio.run(engine.dispose())
            except Exception:
                pass


@pytest.fixture
def cache():
    """Return an explicit InMemoryCache instance for tests.

    Tests should request the `cache` fixture and pass it to `get_repositories`
    or rely on the app state cache_client being set by the session fixture.
    """
    return InMemoryCache()


async def create_tenant_and_user_direct(
    AsyncSessionLocal, tenant_name: str, email: str, password: str, role: str = "admin"
):
    """
    Helper to create a tenant and user directly in the database for tests.

    Returns dict with tenant_id, user_id, email, tenant_name.
    Since /auth/register was removed, tests should use this helper or
    the proper admin flow via /tenants + /tenants/:id/users.
    """
    from src.app.domain.tenant import Tenant
    from src.app.infrastructure.repositories import get_repositories
    from src.app.services.user_service import UserService

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]
        user_repo = repos["users"]

        # Create tenant
        tenant = Tenant(
            id=None,
            name=tenant_name,
            slug=tenant_name.lower().replace(" ", "-"),
            status="active",
            plan="free",
        )
        created_tenant = await tenant_repo.create(tenant)
        await session.commit()

        # Create user
        user_svc = UserService(user_repo, None)
        created_user = await user_svc.create_user(
            int(created_tenant.id), email, password, role=role
        )
        await session.commit()

        return {
            "tenant_id": int(created_tenant.id),
            "user_id": int(created_user.id),
            "id": int(created_user.id),  # For backward compatibility
            "email": email,
            "tenant_name": tenant_name,
        }
