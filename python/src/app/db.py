from typing import Any, Optional, cast

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .config import Settings

# Database engine and session factory (NOT related to user authentication sessions)
# These are SQLAlchemy database sessions for transaction management
engine: Optional[Any] = None
AsyncDbSessionFactory: Any = None

# Backward compatibility alias (deprecated - use AsyncDbSessionFactory)
AsyncSessionLocal: Any = None


def create_engine(settings: Settings) -> Any:
    """Create and return an async engine for the given settings and register it
    on the module so other modules (or tests) can rebind or inspect it.

    Connection Pool Configuration:
    - pool_size: Number of connections to maintain (default: 20)
    - max_overflow: Additional connections when pool exhausted (default: 30)
    - Total max connections: pool_size + max_overflow = 50
    - pool_recycle: Recycle connections after N seconds (prevents stale connections)
    - pool_pre_ping: Test connection health before use (auto-reconnect on failure)
    - command_timeout: 30-second query timeout (PostgreSQL only)
    """
    global engine
    # Allow a full DATABASE URL override (useful for tests)
    if settings.database_url:
        database_url = settings.database_url
    else:
        database_url = f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"

    # Only add command_timeout for PostgreSQL (asyncpg driver supports it)
    # SQLite doesn't support this parameter
    connect_args = {}
    if "postgresql" in database_url:
        connect_args["command_timeout"] = 30  # 30-second statement timeout

    engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=settings.db_pool_pre_ping,
        connect_args=connect_args,
    )
    return engine


def create_sessionmaker(bind_engine: Any) -> Any:
    """Create and register a SQLAlchemy AsyncSession factory (for database transactions)
    bound to the provided engine.

    Note: This creates DATABASE sessions for SQL transactions, not user authentication sessions.
    """
    global AsyncDbSessionFactory, AsyncSessionLocal
    AsyncDbSessionFactory = cast(
        Any, sessionmaker(bind=bind_engine, expire_on_commit=False, class_=AsyncSession)
    )  # type: ignore[call-overload]
    # Maintain backward compatibility
    AsyncSessionLocal = AsyncDbSessionFactory
    return AsyncDbSessionFactory


async def get_db():
    """Dependency that yields a database session for use in route handlers.

    Note: This provides a SQLAlchemy database session for transaction management,
    NOT a user authentication session. User sessions (login/auth) are managed separately
    via JWT tokens and cached in Redis.
    """
    # Resolve the module-level AsyncDbSessionFactory at call time so tests that rebind
    # the module-level value are respected.
    if AsyncDbSessionFactory is None:
        raise RuntimeError(
            "Database session factory not initialized. Call create_engine()/create_sessionmaker() in your application startup."
        )
    async with AsyncDbSessionFactory() as db_session:
        yield db_session
