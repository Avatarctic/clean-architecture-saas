import pytest

from src.app.infrastructure.cache.redis_client import InMemoryCache
from src.app.infrastructure.repositories import get_repositories


@pytest.mark.asyncio
async def test_user_cache_get_and_invalidate(test_app):
    client, engine, AsyncSessionLocal = test_app
    cache = InMemoryCache()

    # create user in DB
    async with AsyncSessionLocal() as session:
        from src.app.infrastructure.db import models

        # ensure tenant exists
        t = models.TenantModel(name="u1", slug="u1")
        session.add(t)
        await session.flush()
        u = models.UserModel(
            tenant_id=t.id,
            first_name="A",
            last_name="B",
            email="u@example.com",
            hashed_password="x",
        )
        session.add(u)
        await session.commit()
        uid = u.id

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=cache)
        users = repos["users"]

        u1 = await users.get_by_id(uid)
        assert u1 is not None

        # cache should return for email lookup
        u2 = await users.get_by_email(u1.tenant_id, "u@example.com")
        assert u2 is not None

        # delete should invalidate cache
        await users.delete(uid)
        u_after = await users.get_by_id(uid)
        assert u_after is None
