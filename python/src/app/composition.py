from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class WireResult:
    app: Any
    engine: Any
    sessionmaker: Any
    teardown: Any


from fastapi import FastAPI

from . import db as db_mod
from .config import Settings
from .logging_config import get_logger
from .setup_db import create_all

logger = get_logger(__name__)


async def wire_app(app: FastAPI) -> WireResult:
    """Run runtime wiring previously inlined in main.on_startup.

    This sets app.state clients, registers them on the `deps` module (and any
    other loaded module objects that expose the expected attributes), builds
    the DB engine and sessionmaker using the public factories in `db`, and
    finally runs `create_all` to ensure tables exist.

    IMPORTANT: This function creates the DB engine, so it MUST NOT be called
    at module import time. Tests rely on setting DATABASE_URL before any
    engines are created. The app.on_event("startup") decorator ensures this
    runs at the right time.
    """
    # instantiate Settings at runtime (avoid module-level side-effects)
    settings = Settings()  # type: ignore[call-arg]

    # initialize redis client and email sender; assume adapters are available
    from .infrastructure.cache.redis_client import AioredisClient, InMemoryCache

    cache_client: Any = InMemoryCache()
    if settings.redis_url:
        cache_client = AioredisClient(settings.redis_url)
        logger.info("initialized redis cache client", redis_url=settings.redis_url)

    app.state.cache_client = cache_client
    from .deps import providers as _providers

    _providers._app_cache_client = cache_client  # type: ignore[attr-defined]

    # email sender (require the infrastructure adapter to exist in stable env)
    from .infrastructure.email.mock import MockEmailSender

    email_sender: Any = MockEmailSender()
    if settings.sendgrid_api_key:
        from .infrastructure.email.sendgrid import SendGridEmailSender

        email_sender = SendGridEmailSender()

    app.state.email_sender = email_sender
    from .deps import providers as _providers

    _providers._app_email_sender = email_sender  # type: ignore[attr-defined]

    logger.info("initialized email sender and cache client")

    # create DB engine/sessionmaker at startup and create tables
    # Build engine and session factory from settings and register them on the db module
    db_engine = db_mod.create_engine(settings)
    db_mod.create_sessionmaker(db_engine)

    # Optionally run Alembic migrations first if AUTO_MIGRATE is enabled
    if os.environ.get("AUTO_MIGRATE", "false").lower() in ("1", "true", "yes"):
        from alembic import command, config

        cfg = config.Config("python/alembic.ini")
        # prefer an explicit DATABASE_URL env var if present
        if os.environ.get("DATABASE_URL"):
            db_url = os.environ.get("DATABASE_URL")
            if db_url is not None:
                cfg.set_main_option("sqlalchemy.url", str(db_url))
        command.upgrade(cfg, "head")

    # create tables using the engine we just created
    await create_all(engine=db_engine)

    # provide a small teardown helper that tests can call to explicitly close
    # long-lived clients and dispose the engine if they created an ephemeral one.
    async def _teardown():
        try:
            redis = getattr(app.state, "cache_client", None)
            if redis:
                try:
                    await redis.client.close()
                except Exception as e:
                    logger.debug("redis_client_close_failed", extra={"error": str(e)})
        except Exception as e:
            logger.debug("teardown_redis_check_failed", extra={"error": str(e)})
        try:
            engine = getattr(db_mod, "engine", None)
            if engine:
                try:
                    await engine.dispose()
                except Exception as e:
                    logger.debug("engine_dispose_failed", extra={"error": str(e)})
        except Exception as e:
            logger.debug("teardown_engine_check_failed", extra={"error": str(e)})

    # schedule optional background purge task for refresh tokens
    # run in background and cancel on teardown
    try:
        from asyncio import create_task, sleep

        settings = Settings()  # type: ignore[call-arg]

        async def _purge_loop():
            # create a dedicated session per purge iteration
            from .infrastructure.repositories.tokens_repository import (
                SqlAlchemyTokensRepository,
            )

            while True:
                try:
                    async with db_mod.AsyncSessionLocal() as session:
                        repo = SqlAlchemyTokensRepository(session)
                        deleted = await repo.purge_refresh_tokens(
                            keep_revoked_for_seconds=getattr(
                                settings,
                                "refresh_token_purge_keep_revoked_seconds",
                                None,
                            )
                        )
                        logger.info("refresh_token_purge_completed", deleted=deleted)
                except Exception as e:
                    try:
                        logger.exception("refresh_token_purge_failed", extra={"error": str(e)})
                    except Exception:
                        pass
                # sleep for configured interval
                try:
                    await sleep(getattr(settings, "refresh_token_cleanup_interval_seconds", 86400))
                except Exception as e:
                    # If cancelled, exit loop
                    try:
                        logger.debug("purge_sleep_interrupted", extra={"error": str(e)})
                    except Exception:
                        pass
                    break

        purge_task = create_task(_purge_loop())

        async def _teardown_with_purge():
            try:
                purge_task.cancel()
                try:
                    await purge_task
                except Exception as e:
                    logger.debug("purge_task_join_failed", extra={"error": str(e)})
            except Exception as e:
                logger.debug("purge_task_cancel_failed", extra={"error": str(e)})
            # call original teardown
            try:
                await _teardown()
            except Exception as e:
                logger.exception("teardown_with_purge_failed", extra={"error": str(e)})

        # expose the augmented teardown
        return WireResult(
            app=app,
            engine=getattr(db_mod, "engine", None),
            sessionmaker=getattr(db_mod, "AsyncSessionLocal", None),
            teardown=_teardown_with_purge,
        )
    except Exception as e:
        # fallback: return original teardown if any errors — log for diagnostics
        logger.exception("wire_app_setup_failed", extra={"error": str(e)})
        return WireResult(
            app=app,
            engine=getattr(db_mod, "engine", None),
            sessionmaker=getattr(db_mod, "AsyncSessionLocal", None),
            teardown=_teardown,
        )
