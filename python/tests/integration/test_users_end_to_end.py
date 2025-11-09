import hashlib

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_users_real_http_flow_and_session_cache(test_app, monkeypatch):
    client, engine, AsyncSessionLocal = test_app
    email = "realflow@example.com"
    password = "pass"

    # Create tenant and user directly (register endpoint was removed)
    from tests.conftest import create_tenant_and_user_direct

    created = await create_tenant_and_user_direct(
        AsyncSessionLocal, tenant_name="tf", email=email, password=password, role="admin"
    )
    created["id"]
    tid = created["tenant_id"]

    # Obtain token via login
    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        r = await http.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200
        tok = r.json()
        access = tok.get("access_token")
        refresh = tok.get("refresh_token")
        assert access is not None and refresh is not None

    # Mock permission repository to return required permissions for this test
    # (test DB doesn't have role-permission seed data)
    from src.app.infrastructure.repositories import get_repositories

    original_get_repositories = get_repositories

    def mock_get_repositories(session, cache=None):
        repos = original_get_repositories(session, cache)

        # Wrap the permissions repository
        original_perms_repo = repos["permissions"]

        class MockPermissionsRepo:
            async def list_user_permissions(self, user_id: int):
                # Return permissions needed for the test
                return [
                    "read_tenant_users",
                    "create_tenant_user",
                    "view_own_sessions",
                    "read_own_profile",
                    "update_own_profile",
                ]

            def __getattr__(self, name):
                return getattr(original_perms_repo, name)

        repos["permissions"] = MockPermissionsRepo()
        return repos

    # Temporarily replace get_repositories
    import src.app.infrastructure.repositories as repos_module

    repos_module.get_repositories = mock_get_repositories

    try:
        # call GET /api/v1/users with auth header
        headers = {"Authorization": f"Bearer {access}"}
        async with AsyncClient(
            transport=ASGITransport(app=client.app), base_url="http://testserver"
        ) as http:
            r = await http.get("/api/v1/users", params={"tenant_id": int(tid)}, headers=headers)
            if r.status_code != 200:
                print("GET /api/v1/users failed:", r.status_code, r.text)
            assert r.status_code == 200
            data = r.json()
            assert isinstance(data, list)

            # create another user in tenant (create lower role to satisfy role-hierarchy)
            r2 = await http.post(
                "/api/v1/users",
                json={
                    "email": "newuser@example.com",
                    "password": "p",
                    "role": "guest",
                },
                headers=headers,
            )
            if r2.status_code != 200:
                print("POST /api/v1/users failed:", r2.status_code, r2.text)
            assert r2.status_code == 200
            data2 = r2.json()
            assert data2["email"] == "newuser@example.com"

        # session cache: check refresh token hash stored
        token_hash = hashlib.sha256(refresh.encode("utf-8")).hexdigest()
        cache = client.app.state.cache_client
        session_val = await cache.get(f"session:{token_hash}")
        assert session_val is not None
    finally:
        # Restore original get_repositories
        repos_module.get_repositories = original_get_repositories


@pytest.mark.asyncio
async def test_role_hierarchy_denies_creating_higher_role(test_app, monkeypatch):
    client, engine, AsyncSessionLocal = test_app
    email = "roletest@example.com"
    password = "pass"

    # Create tenant and user directly (register endpoint was removed)
    from tests.conftest import create_tenant_and_user_direct

    created = await create_tenant_and_user_direct(
        AsyncSessionLocal, tenant_name="rht", email=email, password=password, role="admin"
    )
    tid = created["tenant_id"]

    # Obtain token via login
    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        r = await http.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200
        tok = r.json()
        access = tok.get("access_token")

    # Mock permission repository to return create_tenant_user permission
    # (test DB doesn't have role-permission seed data)
    from src.app.infrastructure.repositories import get_repositories

    original_get_repositories = get_repositories

    def mock_get_repositories(session, cache=None):
        repos = original_get_repositories(session, cache)

        original_perms_repo = repos["permissions"]

        class MockPermissionsRepo:
            async def list_user_permissions(self, user_id: int):
                return ["create_tenant_user"]

            def __getattr__(self, name):
                return getattr(original_perms_repo, name)

        repos["permissions"] = MockPermissionsRepo()
        return repos

    import src.app.infrastructure.repositories as repos_module

    repos_module.get_repositories = mock_get_repositories

    try:
        headers = {"Authorization": f"Bearer {access}"}
        async with AsyncClient(
            transport=ASGITransport(app=client.app), base_url="http://testserver"
        ) as http:
            # attempt to create a user with role 'admin' while caller is 'member'
            r = await http.post(
                "/api/v1/users",
                params={
                    "tenant_id": tid,
                    "email": "admintry@example.com",
                    "password": "p",
                    "role": "admin",
                },
                headers=headers,
            )
            if r.status_code != 403:
                print("POST /api/v1/users (admin try) returned:", r.status_code, r.text)
            assert r.status_code == 403
    finally:
        repos_module.get_repositories = original_get_repositories
