import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import TEST_PASSWORD

# test_app fixture provides the test client; create_test_app import not needed


@pytest.mark.anyio
async def test_rate_limiter_trips(test_app, monkeypatch):
    client, engine, AsyncSessionLocal = test_app

    # Create a test user first
    from tests.conftest import create_tenant_and_user_direct

    await create_tenant_and_user_direct(
        AsyncSessionLocal, "rate_test", "u@example.com", TEST_PASSWORD, "admin"
    )

    # monkeypatch cache to a fresh InMemoryCache
    from src.app.infrastructure.cache.redis_client import InMemoryCache

    cache = InMemoryCache()

    async def _get_cache():
        return cache

    # put the test cache on app.state so middleware reads it
    client.app.state.cache_client = cache
    client.app.dependency_overrides.update({"get_cache_client": _get_cache})

    async with AsyncClient(transport=ASGITransport(app=client.app), base_url="http://test") as ac:
        # Test rate limiting on login endpoint (changed from /auth/token to /auth/login)
        for i in range(12):
            resp = await ac.post(
                "/api/v1/auth/login", json={"email": "u@example.com", "password": TEST_PASSWORD}
            )
            if i < 10:
                assert resp.status_code != 429
            else:
                assert resp.status_code == 429
