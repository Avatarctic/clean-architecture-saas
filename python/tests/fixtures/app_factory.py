import asyncio
import importlib
from types import SimpleNamespace
from typing import Any, Tuple

from src.app import db as db_mod
from src.app.infrastructure.cache.redis_client import InMemoryCache
from src.app.infrastructure.db import models as _models
from src.app.wiring import create_app


def create_test_app(
    database_url: str = None, cache=None, include_middleware: bool = True
) -> Tuple[Any, Any, Any]:
    """Create a TestClient backed by a fresh engine/sessionmaker.

    Args:
        database_url: Optional database URL (defaults to env/conftest settings)
        cache: Optional cache instance (defaults to InMemoryCache)
        include_middleware: If True (default), creates app with full middleware stack
                           including CurrentUserMiddleware. Set to False only for tests
                           that explicitly mock request.state attributes.

    Returns (client, engine, AsyncSessionLocal)

    IMPORTANT: By default, this creates an app WITH CurrentUserMiddleware registered.
    This ensures request.state.tenant and request.state.current_user are properly
    populated during requests. If your test needs to bypass middleware, set
    include_middleware=False and manually mock request.state.tenant/current_user.
    """
    # create settings object if needed; composition root create_app will create Settings itself
    app = create_app()

    # Build an engine for tests if provided a database_url, otherwise rely on env / default
    if database_url:
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(database_url, echo=False)
    else:
        engine = getattr(db_mod, "engine", None)

    if engine is None:
        # If no engine present, leave it to tests to create and manage
        AsyncSessionLocal = None
    else:
        # Ensure tables exist on the ephemeral engine so requests see the schema
        async def _create_tables():
            async with engine.begin() as conn:
                await conn.run_sync(_models.Base.metadata.create_all)

        try:
            asyncio.run(_create_tables())
        except Exception:
            # If running inside an already running event loop (rare in pytest),
            # fall back to scheduling the coroutine — tests will typically run
            # in a fresh loop so this is mostly defensive.
            import anyio

            anyio.run(_create_tables)

        AsyncSessionLocal = db_mod.create_sessionmaker(engine)

        # override get_db dependency so routes use the test sessionmaker
        async def _override_get_db():
            async with AsyncSessionLocal() as session:
                yield session

        # import deps and override
        deps_mod = importlib.import_module("src.app.deps")
        deps_mod.get_db = _override_get_db
        # also set FastAPI dependency_overrides for any routes that captured the original
        try:
            # the original get_db callable used by routes may have been the function
            # object from src.app.deps.get_db; override that mapping too
            orig = deps_mod.get_db
            app.dependency_overrides[orig] = _override_get_db
        except Exception:
            pass

    # Return a lightweight object that exposes the FastAPI app as `.app`.
    # Tests build an httpx.ASGITransport from client.app and don't require
    # the full TestClient functionality, and this avoids compatibility
    # issues between installed starlette/httpx versions.
    client = SimpleNamespace(app=app)
    # Ensure deps.get_cache_client() returns the same cache instance used by the app
    try:
        # If caller provided an explicit cache, attach it to app.state so
        # deps.get_cache_client() can prefer the app-level client during tests.
        if cache is not None:
            try:
                app.state.cache_client = cache
            except Exception:
                pass
        else:
            # Ensure the test app has an explicit in-memory cache client so tests
            # don't rely on dynamic fallbacks. If the wiring layer didn't set a
            # cache_client, create a fresh InMemoryCache and attach it to app.state.
            if not hasattr(app.state, "cache_client") or app.state.cache_client is None:
                try:
                    app.state.cache_client = InMemoryCache()
                except Exception:
                    # non-fatal: if InMemoryCache cannot be constructed for some reason,
                    # leave app.state.cache_client as-is (None) and let tests decide.
                    pass
        # Set cache in both deps and deps.providers modules for compatibility
        deps_mod = importlib.import_module("src.app.deps")
        deps_mod._app_cache_client = getattr(app.state, "cache_client", None)
        try:
            providers_mod = importlib.import_module("src.app.deps.providers")
            providers_mod._app_cache_client = getattr(app.state, "cache_client", None)
        except Exception:
            pass
    except Exception:
        pass
    return client, engine, AsyncSessionLocal


def mock_request_state(request, tenant=None, current_user=None):
    """Helper to mock request.state.tenant and request.state.current_user for tests.

    Use this ONLY when testing with include_middleware=False or when testing
    code paths that don't go through the full ASGI request lifecycle.

    Example:
        from starlette.requests import Request
        from src.app.domain.auth import TokenClaims
        from src.app.domain.tenant import Tenant

        scope = {"type": "http", "method": "GET", "path": "/"}
        request = Request(scope)

        # Mock a tenant and authenticated user
        tenant = Tenant(id=1, name="Acme", slug="acme")
        claims = TokenClaims(subject="123", tenant_id=1)
        mock_request_state(request, tenant=tenant, current_user=claims)

        # Now request.state.tenant and request.state.current_user are set
    """
    if not hasattr(request, "state"):
        # Create a minimal state object if not present
        from starlette.datastructures import State

        request.state = State()

    request.state.tenant = tenant
    request.state.current_user = current_user
