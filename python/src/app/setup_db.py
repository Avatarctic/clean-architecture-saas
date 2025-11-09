from sqlalchemy.ext.asyncio import AsyncEngine

from . import db as db_mod
from .infrastructure.db.models import Base
from .logging_config import get_logger

logger = get_logger(__name__)


async def create_all(engine: AsyncEngine | None = None):
    """Create database tables using the configured async engine.

    On failure we log a clearer, actionable message so developers running the app
    locally understand how to fix it (start the DB with docker-compose or set
    DATABASE_URL to a reachable DB or sqlite file).
    """
    try:
        # Use the provided engine if given, otherwise use the module-level engine
        use_engine = engine or getattr(db_mod, "engine", None)
        if use_engine is None:
            raise RuntimeError("No engine available to create tables")
        # Use SQLAlchemy async engine to run create_all synchronously in the engine's thread
        async with use_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        # Provide a friendly, actionable hint for local development when DB host is unreachable.
        # Use a concise error log so the startup output is actionable and not flooded with a
        # long traceback; keep the full exception at DEBUG level for developers who need it.
        logger.error(
            "create_all failed during startup; could not connect to the configured database."
            " Ensure your database is running (eg. `docker compose up -d`) or set a valid"
            " DATABASE_URL or FALLBACK_DATABASE_URL to use a local sqlite file.",
            error=str(exc),
        )
        # Only log the full traceback when explicitly requested via an environment
        # variable. This prevents noisy long tracebacks from appearing during
        # normal local development when we intentionally fall back to sqlite.
        import os

        if os.environ.get("LOG_FULL_STACK", "").lower() in ("1", "true", "yes"):
            logger.debug("original exception detail", exc_info=exc)
        # If running in CI pipelines or GitHub Actions, fail hard so integrated jobs don't silently
        # fall back to sqlite. Detect common CI env vars.
        import os

        ci_mode = os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")
        if ci_mode:
            logger.error("Running in CI; aborting startup because database is unreachable.")
            raise

        # Not in CI: fall back to SQLite for local development to make startup easier.
        try:
            from .config import Settings

            sqlite_url = os.environ.get("FALLBACK_DATABASE_URL") or "sqlite+aiosqlite:///./dev.db"
            logger.info(
                "Falling back to local sqlite database for development",
                sqlite_url=sqlite_url,
            )

            # Create fallback settings and use db module's create_engine helper
            fallback_settings = Settings(database_url=sqlite_url)  # type: ignore[call-arg]
            new_engine = db_mod.create_engine(fallback_settings)
            db_mod.create_sessionmaker(new_engine)

            # create tables on the fallback engine
            # If a previous sqlite file exists it may have an older schema; drop existing
            # tables first so create_all produces the current model definition. This
            # keeps local development and tests deterministic when falling back to sqlite.
            async with new_engine.begin() as conn:
                # best-effort drop of existing tables to avoid stale columns (eg. tenants.slug)
                try:
                    await conn.run_sync(Base.metadata.drop_all)
                except Exception as e:
                    # ignore drop errors and proceed to create_all, but log at debug
                    try:
                        logger.debug("sqlite_drop_all_failed", extra={"error": str(e)})
                    except Exception:
                        pass
                await conn.run_sync(Base.metadata.create_all)

            logger.info("Successfully switched to local sqlite fallback database")
        except Exception as e:
            try:
                logger.exception(
                    "Failed to initialize sqlite fallback database",
                    extra={"error": str(e)},
                )
            except Exception:
                pass
            raise
