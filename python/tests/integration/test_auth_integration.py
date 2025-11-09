import hashlib

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_login_creates_session(test_app):
    """Test that login creates a session in cache."""
    client, engine, AsyncSessionLocal = test_app

    # Create user directly via service layer (no /register endpoint)
    from tests.conftest import create_tenant_and_user_direct

    await create_tenant_and_user_direct(
        AsyncSessionLocal, "t1", "i@example.com", TEST_PASSWORD, "admin"
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # obtain token via login (changed from /auth/token to /auth/login)
        r = await http.post(
            "/api/v1/auth/login", json={"email": "i@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        tok = r.json()
        assert "access_token" in tok
        assert "refresh_token" in tok

    # check session persisted in cache (session:{token_hash})
    refresh_token = tok.get("refresh_token")
    assert refresh_token is not None
    token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
    cache = client.app.state.cache_client
    # InMemoryCache.get is async
    session_val = await cache.get(f"session:{token_hash}")
    assert session_val is not None

    # engine disposal and tmp_path cleanup handled by fixtures
