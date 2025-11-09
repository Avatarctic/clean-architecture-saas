import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.app.domain.user import User
from src.app.infrastructure.cache.redis_client import InMemoryCache
from src.app.infrastructure.db.models import Base
from src.app.infrastructure.repositories import get_repositories


@pytest.mark.asyncio
async def test_session_create_and_revoke(tmp_path):
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        repo = repos["users"]
        # create fake user
        user = User(
            id=None,
            tenant_id=1,
            email="a@example.com",
            hashed_password="x",
            is_active=True,
        )
        # create tenant first
        from src.app.domain.tenant import Tenant

        t = Tenant(id=None, name="t1")
        tenant_repo = repos["tenants"]
        await tenant_repo.create(t)
        # now create user
        await repo.create(user)
        # create session in cache (sessions are stored in Redis/InMemory, not DB)
        session_id = "sess-1"
        cache = InMemoryCache()
        # In production the value would be the access token; store a placeholder
        await cache.set(f"session:{session_id}", "access-token")
        val = await cache.get(f"session:{session_id}")
        assert val == "access-token"

        # revoke/delete session
        await cache.delete(f"session:{session_id}")
        val = await cache.get(f"session:{session_id}")
        assert val is None
