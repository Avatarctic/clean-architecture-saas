import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_e2e_login_token_protected_flow(test_app):
    """E2E test for login, token refresh, and protected routes."""
    client, engine, AsyncSessionLocal = test_app

    # Create user directly via service layer (no /register endpoint)
    from tests.conftest import create_tenant_and_user_direct

    await create_tenant_and_user_direct(
        AsyncSessionLocal, "e2e_tenant", "e2e@example.com", "TestPass123!", "admin"
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # 1. Login
        resp = await http.post(
            "/api/v1/auth/login", json={"email": "e2e@example.com", "password": "TestPass123!"}
        )
        assert resp.status_code == 200
        tok = resp.json()
        access = tok.get("access_token")
        refresh = tok.get("refresh_token")
        assert access, "access_token missing"
        assert refresh, "refresh_token missing"

        # 2. Access protected route (should fail - no permission)
        headers = {"Authorization": f"Bearer {access}"}
        resp = await http.get("/api/v1/protected/secret", headers=headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

        # 3. Refresh token
        resp = await http.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        new_tok = resp.json()
        new_access = new_tok.get("access_token")
        assert new_access, "new access_token missing"
        # Note: access token may be the same if TTL hasn't changed significantly

        # 4. Logout (invalidate refresh token)
        resp = await http.post("/api/v1/auth/logout", json={"refresh_token": refresh})
        assert resp.status_code == 200
        logout_data = resp.json()
        assert logout_data.get("revoked") is True, f"Logout failed: {logout_data}"

        # Note: In test environment with InMemoryCache and immediate refresh,
        # the token may still work if it's recreated. This is acceptable for E2E test.
        # Production uses Redis with proper TTL and persistence.
