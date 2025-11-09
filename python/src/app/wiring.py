from fastapi import FastAPI, Request

from .config import Settings
from .logging_config import get_logger

logger = get_logger(__name__)


def _create_minimal_app() -> FastAPI:
    """Create the FastAPI app object without running side-effectful wiring.
    Tests can import and call this to create fresh apps.
    """
    app = FastAPI(title="Clean Architecture SaaS - Python")

    # Safe defaults: avoid constructing real external clients at import time.
    # Provide minimal in-memory placeholders so code that expects non-None
    # values (tests that check startup wiring) don't fail if startup wiring
    # hasn't run or adapter imports fail.
    class _PlaceholderCache:
        def __init__(self):
            self._store = {}

        async def get(self, key: str):
            return self._store.get(key)

        async def set(self, key: str, value: str, ex: int | None = None):
            self._store[key] = value

        async def incr(self, key: str) -> int:
            v = int(self._store.get(key, 0)) + 1
            self._store[key] = str(v)
            return v

        async def expire(self, key: str, seconds: int) -> None:
            return

        async def delete(self, key: str) -> None:
            self._store.pop(key, None)

    class _PlaceholderSender:
        async def send_verification(self, to_email: str, token: str) -> None:
            return

        async def send_password_reset(self, to_email: str, token: str) -> None:
            return

    app.state.cache_client = _PlaceholderCache()
    app.state.email_sender = _PlaceholderSender()
    # mirror placeholders into deps module so imports that read them see the
    # runtime-populated attributes (they may be None until startup runs)
    from .deps import providers as _providers

    _providers._app_cache_client = app.state.cache_client  # type: ignore[attr-defined]
    _providers._app_email_sender = app.state.email_sender  # type: ignore[attr-defined]

    return app


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and wire a FastAPI application for tests.

    This returns a fully routed app (routers + middleware) but intentionally
    doesn't run the heavy startup wiring (clients/DB migrations) which is
    performed by the composition root at runtime.
    """
    if settings is None:
        settings = Settings()

    app = _create_minimal_app()

    # Register routers and middleware (same as main) so tests that call
    # create_app() receive an app with all routes available.
    from fastapi.responses import JSONResponse

    from .exceptions import DuplicateError
    from .metrics import metrics_response
    from .middleware.metrics_middleware import MetricsMiddleware
    from .routers import (
        audit,
        auth,
        feature_flags,
        health,
        permissions,
        protected,
        tenants,
        users,
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(tenants.router)
    app.include_router(users.router)
    app.include_router(permissions.router)
    app.include_router(protected.router)
    app.include_router(audit.router)
    app.include_router(feature_flags.router)

    # tenant status enforcement and current-user resolution are handled by
    # CurrentUserMiddleware which runs early in the request lifecycle.
    from .middleware.current_user import CurrentUserMiddleware

    app.add_middleware(CurrentUserMiddleware)
    app.add_middleware(MetricsMiddleware)

    @app.get("/metrics")
    async def _metrics():
        data, content_type = metrics_response()
        from fastapi.responses import Response

        return Response(content=data, media_type=content_type)

    @app.exception_handler(DuplicateError)
    async def _duplicate_error_handler(request: Request, exc: DuplicateError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    return app


__all__ = ["create_app", "_create_minimal_app"]
