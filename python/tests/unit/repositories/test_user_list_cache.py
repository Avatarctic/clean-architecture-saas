import pytest

from src.app.domain.user import User
from src.app.infrastructure.cache.redis_client import InMemoryCache
from src.app.infrastructure.repositories import get_repositories


@pytest.mark.asyncio
async def test_user_list_cache_hit_and_invalidate(test_app):
    client, engine, AsyncSessionLocal = test_app
    cache = InMemoryCache()

    # create tenant + users in DB
    async with AsyncSessionLocal() as session:
        from src.app.infrastructure.db import models

        t = models.TenantModel(name="ulist", slug="ulist")
        session.add(t)
        await session.flush()
        u1 = models.UserModel(
            tenant_id=t.id,
            first_name="A",
            last_name="A",
            email="u1@example.com",
            hashed_password="x",
        )
        u2 = models.UserModel(
            tenant_id=t.id,
            first_name="B",
            last_name="B",
            email="u2@example.com",
            hashed_password="x",
        )
        session.add_all([u1, u2])
        await session.commit()
        tid = t.id

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=cache)
        users = repos["users"]

        # first call populates user:list:tenant:{tid}
        rows = await users.list_by_tenant(tid)
        assert isinstance(rows, list)
        assert any(getattr(r, "email", None) == "u1@example.com" for r in rows)
        assert any(getattr(r, "email", None) == "u2@example.com" for r in rows)

        # remove users from DB directly to simulate staleness
        from src.app.infrastructure.db import models as m2

        async with AsyncSessionLocal() as s2:
            await s2.execute(m2.UserModel.__table__.delete().where(m2.UserModel.tenant_id == tid))
            await s2.commit()

        # cache should still return rows
        cached = await users.list_by_tenant(tid)
        assert isinstance(cached, list)
        assert len(cached) >= 2

        # invalidate by creating a new user via repository create (which deletes list cache)
        new_user = User(id=None, tenant_id=tid, email="x@example.com", hashed_password="x")
        created = await users.create(new_user)
        fresh = await users.list_by_tenant(tid)
        assert any(getattr(r, "email", None) == "x@example.com" for r in fresh)

        # cleanup
        await users.delete(created.id)
