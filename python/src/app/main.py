# configure logging early so any noisy library messages (e.g. passlib bcrypt warnings)
# are suppressed before other app modules import libraries that may log during import.
from .logging_config import get_logger

_early_logger = get_logger(__name__)

# IMPORTANT: Import composition and db modules but do NOT call any functions that
# create engines/connections at module import time. The composition.wire_app() call
# in on_startup() will handle DB initialization at runtime. This ensures tests can
# set DATABASE_URL before any engines are created.
from . import composition
from .logging_config import get_logger

logger = get_logger(__name__)

# Create app using wiring.create_app() to avoid duplicating router/middleware registration
from .wiring import create_app

app = create_app()


@app.on_event("startup")
async def on_startup():
    # delegate runtime wiring to composition.wire_app to centralize side-effectful
    # startup actions. Tests that call the lighter-weight wiring.create_app()
    # will not execute this function.
    # composition.wire_app now returns a small WireResult; the server startup
    # doesn't need the result, but tests can call composition.wire_app() directly
    # and use the returned teardown helper.
    _ = await composition.wire_app(app)


@app.on_event("shutdown")
async def on_shutdown():
    # close any long-lived clients if present
    redis = getattr(app.state, "cache_client", None)
    if redis:
        try:
            await redis.client.close()
        except Exception as e:
            try:
                logger.debug("redis_client_close_failed_on_shutdown", extra={"error": str(e)})
            except Exception:
                # swallow logging failures during shutdown
                pass
    logger.info("shutdown complete")


if __name__ == "__main__":
    import uvicorn

    # Run using module path so imports resolve (`src` must be on PYTHONPATH / marked as source root)
    uvicorn.run("src.app.main:app", host="127.0.0.1", port=8080, reload=True)
