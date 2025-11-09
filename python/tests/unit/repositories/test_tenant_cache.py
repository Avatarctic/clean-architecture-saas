import pytest

from src.app.infrastructure.cache.redis_client import InMemoryCache
from src.app.infrastructure.repositories import get_repositories


@pytest.mark.asyncio
async def test_tenant_cache_hit_and_invalidate(test_app):
    client, engine, AsyncSessionLocal = test_app
    cache = InMemoryCache()

    # create tenant in DB
    async with AsyncSessionLocal() as session:
        from src.app.infrastructure.db import models

        t = models.TenantModel(name="c1", slug="c1")
        session.add(t)
        await session.commit()
        tid = t.id

    # use repo factory with cache
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=cache)
        tenants = repos["tenants"]

        # first read populates cache
        t1 = await tenants.get_by_id(tid)
        assert t1 is not None

        # directly remove from DB to simulate staleness, but cache should still return
        from src.app.infrastructure.db import models as m2

        async with AsyncSessionLocal() as s2:
            await s2.execute(m2.TenantModel.__table__.delete().where(m2.TenantModel.id == tid))
            await s2.commit()

        # cache hit should still return tenant
        t_cached = await tenants.get_by_id(tid)
        assert t_cached is not None

        # invalidate via delete and ensure cache cleared
        await tenants.delete(tid)
        t_after = await tenants.get_by_id(tid)
        assert t_after is None
