import hashlib

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_delete_session_by_hash_and_sessions_list(test_app):
    """Happy path: create a user, obtain tokens, then DELETE by token_hash and via sessions router."""
    client, engine, AsyncSessionLocal = test_app

    # Create user directly via service layer (no /register endpoint)
    from tests.conftest import create_tenant_and_user_direct

    await create_tenant_and_user_direct(
        AsyncSessionLocal, "t_del", "del@example.com", "pass", "admin"
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # login (changed from /auth/token to /auth/login)
        r = await http.post(
            "/api/v1/auth/login",
            json={"email": "del@example.com", "password": "pass"},
        )
        assert r.status_code == 200
        tok = r.json()
        refresh = tok.get("refresh_token")
        assert refresh is not None

        # compute token hash as the repo uses
        token_hash = hashlib.sha256(refresh.encode("utf-8")).hexdigest()

        cache = client.app.state.cache_client
        # confirm mirrored cache under refresh token hash exists
        val = await cache.get(f"session:{token_hash}")
        assert val is not None

        # DELETE via auth route by token_hash
        resp = await http.delete(f"/api/v1/auth/sessions/{token_hash}")
        assert resp.status_code == 200
        assert resp.json().get("revoked") is True

        # cache should no longer have the mirrored key
        val = await cache.get(f"session:{token_hash}")
        assert val is None

        # create another session to test users router delete (sessions router was removed)
        r = await http.post(
            "/api/v1/auth/login",
            json={"email": "del@example.com", "password": "pass"},
        )
        assert r.status_code == 200
        tok2 = r.json()
        refresh2 = tok2.get("refresh_token")
        token_hash2 = hashlib.sha256(refresh2.encode("utf-8")).hexdigest()

        # Delete using auth sessions endpoint (sessions router was removed)
        resp2 = await http.delete(f"/api/v1/auth/sessions/{token_hash2}")
        assert resp2.status_code == 200
        assert resp2.json().get("revoked") is True


@pytest.mark.asyncio
async def test_delete_nonexistent_session_returns_ok_or_error(test_app):
    """Error case: deleting a non-existent token should not crash the server; it may return 200 with revoked=False or 500; we assert it does not raise 500 unhandled."""
    client, engine, AsyncSessionLocal = test_app
    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        fake_hash = hashlib.sha256(b"not-a-real-token").hexdigest()
        resp = await http.delete(f"/api/v1/auth/sessions/{fake_hash}")
    # API contract: deleting a non-existent token is a graceful no-op
    assert resp.status_code == 200
    j = resp.json()
    assert "revoked" in j
    assert j.get("revoked") is False
