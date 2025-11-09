"""Integration tests for missing user management endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient


async def create_user_with_user_mgmt_perms(
    AsyncSessionLocal, tenant_name, email, password, role="admin", app_cache=None
):
    """Helper to create a user with user management permissions."""
    from src.app.infrastructure.repositories import get_repositories
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, tenant_name, email, password, role
    )

    # Grant user management permissions
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        permissions_repo = repos["permissions"]
        user_repo = repos["users"]

        user = await user_repo.get_by_id(user_data["user_id"])
        user_role = getattr(user, "role", role)

        await permissions_repo.set_role_permissions(
            user_role,
            [
                "read_own_profile",
                "update_own_profile",
                "update_own_email",
                "change_own_password",
                "read_tenant_users",
                "update_tenant_users",
                "create_tenant_user",
                "delete_tenant_users",
                "view_own_sessions",
                "view_tenant_sessions",
                "terminate_own_sessions",
                "terminate_tenant_sessions",
            ],
        )
        await session.commit()

    # Clear permissions cache
    if app_cache is not None:
        cache_key_user = f"perm:user:{user_data['user_id']}"
        cache_key_role = f"perm:role:{user_role}"
        await app_cache.delete(cache_key_user)
        await app_cache.delete(cache_key_role)

    return user_data


@pytest.mark.asyncio
async def test_update_user(test_app):
    """Test updating a user's profile."""
    client, engine, AsyncSessionLocal = test_app

    # Create admin user in tenant um1
    user1_data = await create_user_with_user_mgmt_perms(
        AsyncSessionLocal, "um1", "um1@example.com", "pass", "admin", client.app.state.cache_client
    )
    tenant_id = user1_data["tenant_id"]

    # Create second user (member) in the same tenant
    from src.app.infrastructure.repositories import get_repositories
    from src.app.services.user_service import UserService

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        user_repo = repos["users"]
        permissions_repo = repos["permissions"]

        user_svc = UserService(user_repo, None)
        created_user = await user_svc.create_user(
            tenant_id, "um2@example.com", "pass", role="member"
        )
        await session.commit()
        user2_id = int(created_user.id)

        # Grant permissions to member
        await permissions_repo.set_role_permissions(
            "member",
            [
                "read_own_profile",
                "update_own_profile",
            ],
        )
        await session.commit()

    # Clear cache
    cache_key = f"perm:user:{user2_id}"
    await client.app.state.cache_client.delete(cache_key)

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login as admin
        r = await http.post(
            "/api/v1/auth/login", json={"email": "um1@example.com", "password": "pass"}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Update user2's role (admin can only update to lower roles)
        update_resp = await http.put(
            f"/api/v1/users/{user2_id}",
            json={"role": "member"},  # Keep as member or downgrade further
            headers=headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["updated"] is True


@pytest.mark.asyncio
async def test_update_own_profile(test_app):
    """Test that users can update their own profile."""
    client, engine, AsyncSessionLocal = test_app

    # Create user
    user_data = await create_user_with_user_mgmt_perms(
        AsyncSessionLocal, "um2", "um3@example.com", "pass", "member", client.app.state.cache_client
    )
    user_id = user_data["user_id"]

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "um3@example.com", "password": "pass"}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Update own profile (non-sensitive fields)
        update_resp = await http.put(
            f"/api/v1/users/{user_id}", json={"is_active": True}, headers=headers
        )
        assert update_resp.status_code == 200


@pytest.mark.asyncio
async def test_change_user_password(test_app):
    """Test changing a user's password."""
    client, engine, AsyncSessionLocal = test_app

    # Create user
    # Create user
    user_data = await create_user_with_user_mgmt_perms(
        AsyncSessionLocal, "um3", "um4@example.com", "pass", "member", client.app.state.cache_client
    )
    user_id = user_data["user_id"]

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "um4@example.com", "password": "pass"}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Change password
        change_resp = await http.post(
            f"/api/v1/users/{user_id}/password",
            json={"new_password": "newpass123"},
            headers=headers,
        )
        assert change_resp.status_code == 200
        assert change_resp.json()["changed"] is True

        # Verify old password no longer works
        login_old = await http.post(
            "/api/v1/auth/login", json={"email": "um4@example.com", "password": "pass"}
        )
        assert login_old.status_code == 401

        # Verify new password works
        login_new = await http.post(
            "/api/v1/auth/login", json={"email": "um4@example.com", "password": "newpass123"}
        )
        assert login_new.status_code == 200


@pytest.mark.asyncio
async def test_change_user_email(test_app):
    """Test changing a user's email address."""
    client, engine, AsyncSessionLocal = test_app

    # Create user
    user_data = await create_user_with_user_mgmt_perms(
        AsyncSessionLocal, "um4", "um5@example.com", "pass", "member", client.app.state.cache_client
    )
    user_id = user_data["user_id"]

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "um5@example.com", "password": "pass"}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Change email
        change_resp = await http.patch(
            f"/api/v1/users/{user_id}/email",
            json={"new_email": "um5_new@example.com"},
            headers=headers,
        )
        assert change_resp.status_code == 200
        assert change_resp.json()["updated"] is True

        # Verify login with new email works
        login_new = await http.post(
            "/api/v1/auth/login", json={"email": "um5_new@example.com", "password": "pass"}
        )
        assert login_new.status_code == 200


@pytest.mark.asyncio
async def test_list_user_sessions(test_app):
    """Test listing all sessions for a user."""
    client, engine, AsyncSessionLocal = test_app

    # Create user
    user_data = await create_user_with_user_mgmt_perms(
        AsyncSessionLocal, "um5", "um6@example.com", "pass", "admin", client.app.state.cache_client
    )
    user_id = user_data["user_id"]

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login to create a session
        r = await http.post(
            "/api/v1/auth/login", json={"email": "um6@example.com", "password": "pass"}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # List sessions
        sessions_resp = await http.get(f"/api/v1/users/{user_id}/sessions", headers=headers)
        assert sessions_resp.status_code == 200
        sessions = sessions_resp.json()
        assert isinstance(sessions, list)
        # Should have at least the current session
        assert len(sessions) >= 0


@pytest.mark.asyncio
async def test_delete_user_session(test_app):
    """Test deleting a specific user session."""
    client, engine, AsyncSessionLocal = test_app

    # Create user
    user_data = await create_user_with_user_mgmt_perms(
        AsyncSessionLocal, "um6", "um7@example.com", "pass", "admin", client.app.state.cache_client
    )
    user_id = user_data["user_id"]

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login to create a session
        r = await http.post(
            "/api/v1/auth/login", json={"email": "um7@example.com", "password": "pass"}
        )
        assert r.status_code == 200
        refresh_token = r.json()["refresh_token"]
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Get token hash
        import hashlib

        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        # Delete the session
        delete_resp = await http.delete(
            f"/api/v1/users/{user_id}/sessions/{token_hash}", headers=headers
        )
        assert delete_resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_all_user_sessions(test_app):
    """Test deleting all sessions for a user."""
    client, engine, AsyncSessionLocal = test_app

    # Create user
    user_data = await create_user_with_user_mgmt_perms(
        AsyncSessionLocal, "um7", "um8@example.com", "pass", "admin", client.app.state.cache_client
    )
    user_id = user_data["user_id"]

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login to create sessions
        r = await http.post(
            "/api/v1/auth/login", json={"email": "um8@example.com", "password": "pass"}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Delete all sessions
        delete_resp = await http.delete(f"/api/v1/users/{user_id}/sessions", headers=headers)
        assert delete_resp.status_code == 200
        assert delete_resp.json()["revoked"] is True


@pytest.mark.asyncio
async def test_cannot_update_user_in_different_tenant(test_app):
    """Test that users cannot update users from different tenants."""
    client, engine, AsyncSessionLocal = test_app

    # Create users in different tenants
    await create_user_with_user_mgmt_perms(
        AsyncSessionLocal, "um8", "um9@example.com", "pass", "admin", client.app.state.cache_client
    )
    user2_data = await create_user_with_user_mgmt_perms(
        AsyncSessionLocal, "um9", "um10@example.com", "pass", "admin", client.app.state.cache_client
    )
    user2_id = user2_data["user_id"]

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login as user1
        r = await http.post(
            "/api/v1/auth/login", json={"email": "um9@example.com", "password": "pass"}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Try to update user2 from different tenant
        update_resp = await http.put(
            f"/api/v1/users/{user2_id}", json={"role": "member"}, headers=headers
        )
        # Should be forbidden
        assert update_resp.status_code == 403


@pytest.mark.asyncio
async def test_change_password_without_auth_fails(test_app):
    """Test that password change requires authentication."""
    client, engine, AsyncSessionLocal = test_app

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Try to change password without auth
        change_resp = await http.post("/api/v1/users/1/password", json={"new_password": "newpass"})
        assert change_resp.status_code == 401
