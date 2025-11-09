"""
Integration tests for GET /tenants/{id} and PUT /tenants/{id} endpoints.
Tests the read_own_tenant and update_tenant permissions.
"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_get_own_tenant_with_read_own_tenant_permission(test_app):
    """User with read_own_tenant can get their own tenant"""
    client, engine, SessionLocal = test_app

    # Create a user with specific permissions
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        SessionLocal,
        tenant_name="own_tenant_test",
        email="own@example.com",
        password="testpass",
        role="member",
    )

    # Login to get token
    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://test"
    ) as aclient:
        login_resp = await aclient.post(
            "/api/v1/auth/login", json={"email": "own@example.com", "password": "testpass"}
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Mock permissions to have read_own_tenant
        from src.app.infrastructure.repositories import get_repositories

        original_get_repositories = get_repositories

        def mock_get_repositories(session, cache=None):
            repos = original_get_repositories(session, cache)
            original_perms_repo = repos["permissions"]

            class MockPermissionsRepo:
                async def list_user_permissions(self, user_id: int):
                    return ["read_own_tenant"]

                def __getattr__(self, name):
                    return getattr(original_perms_repo, name)

            repos["permissions"] = MockPermissionsRepo()
            return repos

        import src.app.infrastructure.repositories as repos_module

        repos_module.get_repositories = mock_get_repositories

        try:
            # User should be able to read their own tenant
            headers = {"Authorization": f"Bearer {token}"}
            resp = await aclient.get(f"/api/v1/tenants/{user_data['tenant_id']}", headers=headers)
            assert resp.status_code == 200

            data = resp.json()
            assert data["id"] == user_data["tenant_id"]
        finally:
            repos_module.get_repositories = original_get_repositories


@pytest.mark.asyncio
async def test_get_other_tenant_forbidden_with_read_own_tenant(test_app):
    """User with read_own_tenant cannot get other tenants"""
    client, engine, SessionLocal = test_app

    # Create first user
    from tests.conftest import create_tenant_and_user_direct

    await create_tenant_and_user_direct(
        SessionLocal,
        tenant_name="tenant1",
        email="user1@example.com",
        password="testpass",
        role="member",
    )

    # Create second tenant
    from src.app.domain.tenant import Tenant

    async with SessionLocal() as session:
        from src.app.infrastructure.repositories import get_repositories

        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        tenant2 = Tenant(
            id=None,
            name="Other Corp",
            slug="other",
            plan="basic",
            status="active",
        )
        created_tenant2 = await tenant_repo.create(tenant2)
        await session.commit()
        tenant2_id = int(created_tenant2.id)

    # Login as user1
    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://test"
    ) as aclient:
        login_resp = await aclient.post(
            "/api/v1/auth/login", json={"email": "user1@example.com", "password": "testpass"}
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Mock permissions to have read_own_tenant
        from src.app.infrastructure.repositories import get_repositories

        original_get_repositories = get_repositories

        def mock_get_repositories(session, cache=None):
            repos = original_get_repositories(session, cache)
            original_perms_repo = repos["permissions"]

            class MockPermissionsRepo:
                async def list_user_permissions(self, user_id: int):
                    return ["read_own_tenant"]

                def __getattr__(self, name):
                    return getattr(original_perms_repo, name)

            repos["permissions"] = MockPermissionsRepo()
            return repos

        import src.app.infrastructure.repositories as repos_module

        repos_module.get_repositories = mock_get_repositories

        try:
            # User from tenant1 tries to access tenant2
            headers = {"Authorization": f"Bearer {token}"}
            resp = await aclient.get(f"/api/v1/tenants/{tenant2_id}", headers=headers)
            assert resp.status_code == 403
            assert "Cannot access other tenants" in resp.json()["detail"]
        finally:
            repos_module.get_repositories = original_get_repositories


@pytest.mark.asyncio
async def test_update_tenant_settings(test_app):
    """User with update_tenant can update tenant settings"""
    client, engine, SessionLocal = test_app

    # Create a user
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        SessionLocal,
        tenant_name="update_test",
        email="update@example.com",
        password="testpass",
        role="admin",
    )

    # Login
    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://test"
    ) as aclient:
        login_resp = await aclient.post(
            "/api/v1/auth/login", json={"email": "update@example.com", "password": "testpass"}
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Mock permissions to have update_tenant
        from src.app.infrastructure.repositories import get_repositories

        original_get_repositories = get_repositories

        def mock_get_repositories(session, cache=None):
            repos = original_get_repositories(session, cache)
            original_perms_repo = repos["permissions"]

            class MockPermissionsRepo:
                async def list_user_permissions(self, user_id: int):
                    return ["update_tenant"]

                def __getattr__(self, name):
                    return getattr(original_perms_repo, name)

            repos["permissions"] = MockPermissionsRepo()
            return repos

        import src.app.infrastructure.repositories as repos_module

        repos_module.get_repositories = mock_get_repositories

        try:
            # Update tenant
            headers = {"Authorization": f"Bearer {token}"}
            resp = await aclient.put(
                f"/api/v1/tenants/{user_data['tenant_id']}",
                headers=headers,
                json={
                    "name": "Updated Name",
                    "domain": "updated.example.com",
                    "plan": "enterprise",
                    "settings": {"feature_x": True},
                },
            )
            assert resp.status_code == 200

            data = resp.json()
            assert data["name"] == "Updated Name"
            assert data["domain"] == "updated.example.com"
            assert data["plan"] == "enterprise"
            assert data["settings"] == {"feature_x": True}
        finally:
            repos_module.get_repositories = original_get_repositories


@pytest.mark.asyncio
async def test_update_tenant_status_forbidden(test_app):
    """Cannot update status via PUT endpoint"""
    client, engine, SessionLocal = test_app

    # Create a user
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        SessionLocal,
        tenant_name="status_test",
        email="status@example.com",
        password="testpass",
        role="admin",
    )

    # Login
    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://test"
    ) as aclient:
        login_resp = await aclient.post(
            "/api/v1/auth/login", json={"email": "status@example.com", "password": "testpass"}
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Mock permissions
        from src.app.infrastructure.repositories import get_repositories

        original_get_repositories = get_repositories

        def mock_get_repositories(session, cache=None):
            repos = original_get_repositories(session, cache)
            original_perms_repo = repos["permissions"]

            class MockPermissionsRepo:
                async def list_user_permissions(self, user_id: int):
                    return ["update_tenant"]

                def __getattr__(self, name):
                    return getattr(original_perms_repo, name)

            repos["permissions"] = MockPermissionsRepo()
            return repos

        import src.app.infrastructure.repositories as repos_module

        repos_module.get_repositories = mock_get_repositories

        try:
            # Try to update status
            headers = {"Authorization": f"Bearer {token}"}
            resp = await aclient.put(
                f"/api/v1/tenants/{user_data['tenant_id']}",
                headers=headers,
                json={"status": "suspended"},
            )
            assert resp.status_code == 400
            assert "Cannot update status via this endpoint" in resp.json()["detail"]
        finally:
            repos_module.get_repositories = original_get_repositories
