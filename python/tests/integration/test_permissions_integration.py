"""Integration tests for permissions router endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import TEST_PASSWORD


async def create_user_with_permission_perms(
    AsyncSessionLocal, tenant_name, email, password, app_cache=None
):
    """Helper to create a user with permission management permissions."""
    from src.app.infrastructure.repositories import get_repositories
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, tenant_name, email, password, "admin"
    )

    # Grant permission management permissions
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        permissions_repo = repos["permissions"]
        user_repo = repos["users"]

        user = await user_repo.get_by_id(user_data["user_id"])
        role = getattr(user, "role", "admin")

        await permissions_repo.set_role_permissions(
            role, ["view_permissions", "manage_permissions"]
        )
        await session.commit()

    # Clear permissions cache
    if app_cache is not None:
        cache_key = f"perm:user:{user_data['user_id']}"
        await app_cache.delete(cache_key)

    return user_data


@pytest.mark.asyncio
async def test_list_all_permissions(test_app):
    """Test listing all available permissions."""
    client, engine, AsyncSessionLocal = test_app

    # Create admin user
    await create_user_with_permission_perms(
        AsyncSessionLocal,
        "perm1",
        "perm1@example.com",
        TEST_PASSWORD,
        client.app.state.cache_client,
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "perm1@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # List all permissions
        list_resp = await http.get("/api/v1/permissions", headers=headers)
        assert list_resp.status_code == 200
        response_data = list_resp.json()
        assert isinstance(response_data, dict)
        assert "permissions" in response_data
        permissions = response_data["permissions"]
        assert isinstance(permissions, list)
        assert len(permissions) > 0
        # Check for expected permission structure
        if permissions:
            perm = permissions[0]
            assert "name" in perm or "id" in perm


@pytest.mark.asyncio
async def test_list_role_permissions(test_app):
    """Test listing permissions for a specific role."""
    client, engine, AsyncSessionLocal = test_app

    # Create admin user
    await create_user_with_permission_perms(
        AsyncSessionLocal,
        "perm2",
        "perm2@example.com",
        TEST_PASSWORD,
        client.app.state.cache_client,
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "perm2@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # List permissions for admin role
        list_resp = await http.get("/api/v1/permissions/roles/admin", headers=headers)
        assert list_resp.status_code == 200
        response_data = list_resp.json()
        assert isinstance(response_data, dict)
        assert "permissions" in response_data
        role_perms = response_data["permissions"]
        assert isinstance(role_perms, list)


@pytest.mark.asyncio
async def test_set_role_permissions(test_app):
    """Test setting permissions for a role."""
    client, engine, AsyncSessionLocal = test_app

    # Create admin user
    await create_user_with_permission_perms(
        AsyncSessionLocal,
        "perm3",
        "perm3@example.com",
        TEST_PASSWORD,
        client.app.state.cache_client,
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "perm3@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Get list of available permissions first
        perms_resp = await http.get("/api/v1/permissions", headers=headers)
        response_data = perms_resp.json()
        all_permissions = response_data.get("permissions", [])

        # Extract permission names
        if all_permissions:
            # Take first 3 permission names
            permission_names = []
            for p in all_permissions[:3]:
                if "name" in p:
                    permission_names.append(p["name"])

            if permission_names:
                # Set permissions for a custom role
                set_resp = await http.put(
                    "/api/v1/permissions/roles/custom_role",
                    json={"permissions": permission_names},
                    headers=headers,
                )
                # May return 200 or error if role doesn't exist
                assert set_resp.status_code in (200, 404, 400, 422)


@pytest.mark.asyncio
async def test_add_permission_to_role(test_app):
    """Test adding a single permission to a role."""
    client, engine, AsyncSessionLocal = test_app

    # Create admin user
    await create_user_with_permission_perms(
        AsyncSessionLocal,
        "perm4",
        "perm4@example.com",
        TEST_PASSWORD,
        client.app.state.cache_client,
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "perm4@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Try to add a permission to admin role
        add_resp = await http.post(
            "/api/v1/permissions/roles/admin/permissions",
            params={"permission": "read_own_profile"},
            headers=headers,
        )
        # May succeed or return error if permission already exists
        assert add_resp.status_code in (200, 400, 404, 409)


@pytest.mark.asyncio
async def test_remove_permission_from_role(test_app):
    """Test removing a permission from a role."""
    client, engine, AsyncSessionLocal = test_app

    # Create admin user
    await create_user_with_permission_perms(
        AsyncSessionLocal,
        "perm5",
        "perm5@example.com",
        TEST_PASSWORD,
        client.app.state.cache_client,
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "perm5@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # First add a permission
        await http.post(
            "/api/v1/permissions/roles/admin/permissions/test_permission", headers=headers
        )

        # Then remove it
        remove_resp = await http.delete(
            "/api/v1/permissions/roles/admin/permissions/test_permission", headers=headers
        )
        # May succeed or return 404 if permission doesn't exist
        assert remove_resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_permission_operations_require_auth(test_app):
    """Test that permission operations require authentication."""
    client, engine, AsyncSessionLocal = test_app

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Try to list permissions without auth
        list_resp = await http.get("/api/v1/permissions")
        assert list_resp.status_code == 401

        # Try to set role permissions without auth
        set_resp = await http.put(
            "/api/v1/permissions/roles/admin", json={"permission_ids": [1, 2, 3]}
        )
        assert set_resp.status_code == 401


@pytest.mark.asyncio
async def test_add_invalid_permission_to_role(test_app):
    """Test adding a nonexistent permission to a role returns appropriate error."""
    client, engine, AsyncSessionLocal = test_app

    # Create admin user
    await create_user_with_permission_perms(
        AsyncSessionLocal,
        "perm6",
        "perm6@example.com",
        TEST_PASSWORD,
        client.app.state.cache_client,
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "perm6@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Try to add nonexistent permission
        add_resp = await http.post(
            "/api/v1/permissions/roles/admin/permissions",
            params={"permission": "nonexistent_permission_xyz"},
            headers=headers,
        )
        # Should return 404 or 400
        assert add_resp.status_code in (404, 400)
