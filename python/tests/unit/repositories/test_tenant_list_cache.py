import pytest

from src.app.domain.tenant import Tenant
from src.app.infrastructure.cache.redis_client import InMemoryCache
from src.app.infrastructure.repositories import get_repositories


@pytest.mark.asyncio
async def test_tenant_list_cache_hit_and_invalidate(test_app):
    client, engine, AsyncSessionLocal = test_app
    cache = InMemoryCache()

    # create several tenants in DB
    async with AsyncSessionLocal() as session:
        from src.app.infrastructure.db import models

        t1 = models.TenantModel(name="list1", slug="list1")
        t2 = models.TenantModel(name="list2", slug="list2")
        session.add_all([t1, t2])
        await session.commit()
        tid1 = t1.id
        tid2 = t2.id

    # use repo factory with cache
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=cache)
        tenants = repos["tenants"]

        # first call - populates tenant:list:all cache
        rows = await tenants.list_all()
        assert isinstance(rows, list)
        assert any(getattr(r, "id", None) == tid1 for r in rows)
        assert any(getattr(r, "id", None) == tid2 for r in rows)

        # remove tenants directly from DB to simulate stale DB; cache should still return
        from src.app.infrastructure.db import models as m2

        async with AsyncSessionLocal() as s2:
            await s2.execute(m2.TenantModel.__table__.delete())
            await s2.commit()

        cached_rows = await tenants.list_all()
        assert isinstance(cached_rows, list)
        assert len(cached_rows) >= 2

        # invalidate via create (which should delete tenant:list:all) and check cache is refreshed
        new_t = Tenant(
            id=None,
            name="newt",
            slug="newt",
            domain=None,
            plan="free",
            status="active",
            settings={},
        )
        created = await tenants.create(new_t)
        # after create, list_all should reflect DB state (cache was invalidated)
        fresh = await tenants.list_all()
        assert any(getattr(r, "id", None) == getattr(created, "id", None) for r in fresh)

        # cleanup: remove created tenant
        await tenants.delete(created.id)
