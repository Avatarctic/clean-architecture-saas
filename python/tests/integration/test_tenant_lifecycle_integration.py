"""Integration tests for tenant lifecycle management endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import TEST_PASSWORD


async def create_user_with_tenant_perms(
    AsyncSessionLocal, tenant_name, email, password, role="admin", app_cache=None
):
    """Helper to create a user with tenant management permissions."""
    from src.app.infrastructure.repositories import get_repositories
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, tenant_name, email, password, role
    )

    # Grant tenant management permissions
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        permissions_repo = repos["permissions"]
        user_repo = repos["users"]

        user = await user_repo.get_by_id(user_data["user_id"])
        user_role = getattr(user, "role", role)

        await permissions_repo.set_role_permissions(
            user_role,
            ["create_tenant", "read_all_tenants", "manage_tenant_status", "create_tenant_user"],
        )
        await session.commit()

    # Clear permissions cache
    if app_cache is not None:
        cache_key = f"perm:user:{user_data['user_id']}"
        await app_cache.delete(cache_key)

    return user_data


@pytest.mark.asyncio
async def test_list_all_tenants(test_app):
    """Test listing all tenants (superadmin permission required)."""
    client, engine, AsyncSessionLocal = test_app

    # Create multiple tenants
    await create_user_with_tenant_perms(
        AsyncSessionLocal,
        "tl1",
        "tl1@example.com",
        TEST_PASSWORD,
        "admin",
        client.app.state.cache_client,
    )
    await create_user_with_tenant_perms(
        AsyncSessionLocal,
        "tl2",
        "tl2@example.com",
        TEST_PASSWORD,
        "admin",
        client.app.state.cache_client,
    )
    # Create superadmin user
    await create_user_with_tenant_perms(
        AsyncSessionLocal,
        "platform",
        "superadmin@example.com",
        TEST_PASSWORD,
        "super_admin",
        client.app.state.cache_client,
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login as superadmin
        r = await http.post(
            "/api/v1/auth/login",
            json={"email": "superadmin@example.com", "password": TEST_PASSWORD},
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # List tenants
        list_resp = await http.get("/api/v1/tenants/", headers=headers)
        assert list_resp.status_code == 200
        tenants = list_resp.json()
        assert isinstance(tenants, list)
        assert len(tenants) >= 3  # At least the 3 we created


@pytest.mark.asyncio
async def test_suspend_tenant(test_app):
    """Test suspending a tenant."""
    client, engine, AsyncSessionLocal = test_app

    # Create tenant and superadmin
    from src.app.infrastructure.repositories import get_repositories
    from tests.conftest import create_tenant_and_user_direct

    tenant_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "tl3", "tl3@example.com", TEST_PASSWORD, "admin"
    )
    tenant_id = tenant_data["tenant_id"]
    sa_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "platform", "sa2@example.com", TEST_PASSWORD, "super_admin"
    )
    sa_user_id = sa_data["user_id"]

    # Grant super_admin the manage_tenant_status permission
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        permissions_repo = repos["permissions"]
        await permissions_repo.set_role_permissions("super_admin", ["manage_tenant_status"])
        await session.commit()

    # Clear permissions cache
    app_cache = getattr(client.app.state, "cache", None)
    if app_cache is not None:
        await app_cache.delete(f"user:permissions:{sa_user_id}")

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login as superadmin
        r = await http.post(
            "/api/v1/auth/login", json={"email": "sa2@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Suspend tenant
        suspend_resp = await http.post(f"/api/v1/tenants/{tenant_id}/suspend", headers=headers)
        assert suspend_resp.status_code == 200
        suspended = suspend_resp.json()
        assert suspended["status"] == "suspended"


@pytest.mark.asyncio
async def test_activate_suspended_tenant(test_app):
    """Test activating a suspended tenant."""
    client, engine, AsyncSessionLocal = test_app

    # Create tenant and superadmin
    from src.app.infrastructure.db import models
    from src.app.infrastructure.repositories import get_repositories
    from tests.conftest import create_tenant_and_user_direct

    tenant_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "tl4", "tl4@example.com", TEST_PASSWORD, "admin"
    )
    tenant_id = tenant_data["tenant_id"]

    # Manually set tenant to suspended
    async with AsyncSessionLocal() as session:
        tenant = await session.get(models.TenantModel, tenant_id)
        tenant.status = "suspended"
        await session.commit()

    sa_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "platform", "sa3@example.com", TEST_PASSWORD, "super_admin"
    )
    sa_user_id = sa_data["user_id"]

    # Grant super_admin the manage_tenant_status permission
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        permissions_repo = repos["permissions"]
        await permissions_repo.set_role_permissions("super_admin", ["manage_tenant_status"])
        await session.commit()

    # Clear permissions cache
    app_cache = getattr(client.app.state, "cache", None)
    if app_cache is not None:
        await app_cache.delete(f"user:permissions:{sa_user_id}")

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login as superadmin
        r = await http.post(
            "/api/v1/auth/login", json={"email": "sa3@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Activate tenant
        activate_resp = await http.post(f"/api/v1/tenants/{tenant_id}/activate", headers=headers)
        assert activate_resp.status_code == 200
        activated = activate_resp.json()
        assert activated["status"] == "active"


@pytest.mark.asyncio
async def test_cancel_tenant(test_app):
    """Test canceling a tenant."""
    client, engine, AsyncSessionLocal = test_app

    # Create tenant and superadmin
    from src.app.infrastructure.repositories import get_repositories
    from tests.conftest import create_tenant_and_user_direct

    tenant_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "tl5", "tl5@example.com", TEST_PASSWORD, "admin"
    )
    tenant_id = tenant_data["tenant_id"]
    sa_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "platform", "sa4@example.com", TEST_PASSWORD, "super_admin"
    )
    sa_user_id = sa_data["user_id"]

    # Grant super_admin the manage_tenant_status permission
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        permissions_repo = repos["permissions"]
        await permissions_repo.set_role_permissions("super_admin", ["manage_tenant_status"])
        await session.commit()

    # Clear permissions cache
    app_cache = getattr(client.app.state, "cache", None)
    if app_cache is not None:
        await app_cache.delete(f"user:permissions:{sa_user_id}")

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login as superadmin
        r = await http.post(
            "/api/v1/auth/login", json={"email": "sa4@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Cancel tenant
        cancel_resp = await http.post(f"/api/v1/tenants/{tenant_id}/cancel", headers=headers)
        assert cancel_resp.status_code == 200
        canceled = cancel_resp.json()
        assert canceled["status"] == "canceled"


@pytest.mark.asyncio
async def test_cannot_activate_canceled_tenant(test_app):
    """Test that activating a canceled tenant fails."""
    client, engine, AsyncSessionLocal = test_app

    # Create tenant and superadmin
    from src.app.infrastructure.db import models
    from src.app.infrastructure.repositories import get_repositories
    from tests.conftest import create_tenant_and_user_direct

    tenant_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "tl6", "tl6@example.com", TEST_PASSWORD, "admin"
    )
    tenant_id = tenant_data["tenant_id"]

    # Manually set tenant to canceled
    async with AsyncSessionLocal() as session:
        tenant = await session.get(models.TenantModel, tenant_id)
        tenant.status = "canceled"
        await session.commit()

    sa_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "platform", "sa5@example.com", TEST_PASSWORD, "super_admin"
    )
    sa_user_id = sa_data["user_id"]

    # Grant super_admin the manage_tenant_status permission
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        permissions_repo = repos["permissions"]
        await permissions_repo.set_role_permissions("super_admin", ["manage_tenant_status"])
        await session.commit()

    # Clear permissions cache
    app_cache = getattr(client.app.state, "cache", None)
    if app_cache is not None:
        await app_cache.delete(f"user:permissions:{sa_user_id}")

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login as superadmin
        r = await http.post(
            "/api/v1/auth/login", json={"email": "sa5@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Try to activate canceled tenant
        activate_resp = await http.post(f"/api/v1/tenants/{tenant_id}/activate", headers=headers)
        # Should fail with 400 or 404
        assert activate_resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_tenant_status_changes_require_auth(test_app):
    """Test that tenant status changes require authentication."""
    client, engine, AsyncSessionLocal = test_app

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Try to suspend without auth
        suspend_resp = await http.post("/api/v1/tenants/1/suspend")
        assert suspend_resp.status_code == 401

        # Try to activate without auth
        activate_resp = await http.post("/api/v1/tenants/1/activate")
        assert activate_resp.status_code == 401

        # Try to cancel without auth
        cancel_resp = await http.post("/api/v1/tenants/1/cancel")
        assert cancel_resp.status_code == 401


@pytest.mark.asyncio
async def test_regular_user_cannot_suspend_tenant(test_app):
    """Test that regular users cannot suspend tenants."""
    client, engine, AsyncSessionLocal = test_app

    # Create regular user and tenant
    from tests.conftest import create_tenant_and_user_direct

    tenant_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "tl7", "tl7@example.com", TEST_PASSWORD, "member"
    )
    tenant_id = tenant_data["tenant_id"]

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login as regular user
        r = await http.post(
            "/api/v1/auth/login", json={"email": "tl7@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Try to suspend tenant
        suspend_resp = await http.post(f"/api/v1/tenants/{tenant_id}/suspend", headers=headers)
        # Should be forbidden
        assert suspend_resp.status_code == 403


@pytest.mark.asyncio
async def test_suspend_nonexistent_tenant(test_app):
    """Test suspending a nonexistent tenant returns 404."""
    client, engine, AsyncSessionLocal = test_app

    # Create superadmin
    await create_user_with_tenant_perms(
        AsyncSessionLocal,
        "platform",
        "sa6@example.com",
        TEST_PASSWORD,
        "super_admin",
        client.app.state.cache_client,
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login as superadmin
        r = await http.post(
            "/api/v1/auth/login", json={"email": "sa6@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Try to suspend nonexistent tenant
        suspend_resp = await http.post("/api/v1/tenants/99999/suspend", headers=headers)
        assert suspend_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_user_in_tenant_endpoint(test_app):
    """Test creating a user directly in a tenant."""
    client, engine, AsyncSessionLocal = test_app

    # Create tenant with admin
    from src.app.infrastructure.repositories import get_repositories
    from tests.conftest import create_tenant_and_user_direct

    tenant_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "tl8", "tl8@example.com", TEST_PASSWORD, "admin"
    )
    tenant_id = tenant_data["tenant_id"]
    user_id = tenant_data["user_id"]

    # Grant admin the create_tenant_user permission
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        permissions_repo = repos["permissions"]
        await permissions_repo.set_role_permissions("admin", ["create_tenant_user"])
        await session.commit()

    # Clear permissions cache
    app_cache = getattr(client.app.state, "cache", None)
    if app_cache is not None:
        await app_cache.delete(f"user:permissions:{user_id}")

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login as admin
        r = await http.post(
            "/api/v1/auth/login", json={"email": "tl8@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Create user in tenant
        create_resp = await http.post(
            f"/api/v1/tenants/{tenant_id}/users",
            params={"email": "newuser@example.com", "password": TEST_PASSWORD, "role": "member"},
            headers=headers,
        )
        assert create_resp.status_code == 200
        user = create_resp.json()
        assert user["email"] == "newuser@example.com"
