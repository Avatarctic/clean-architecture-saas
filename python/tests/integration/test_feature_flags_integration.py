"""Integration tests for feature flags router endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import TEST_PASSWORD


async def grant_permissions(AsyncSessionLocal, user_id, permissions):
    """Helper to grant permissions to a user for testing."""
    from src.app.infrastructure.repositories import get_repositories

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        permissions_repo = repos["permissions"]

        # Get user's role
        user_repo = repos["users"]
        user = await user_repo.get_by_id(user_id)
        if not user:
            return

        role = getattr(user, "role", "member")

        # Set permissions for the role (replaces existing)
        await permissions_repo.set_role_permissions(role, permissions)

        await session.commit()


async def create_user_with_ff_permissions(
    AsyncSessionLocal, tenant_name, email, password, app_cache=None
):
    """Helper to create a user with all feature flag permissions."""
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, tenant_name, email, password, "admin"
    )

    # Grant all feature flag permissions
    await grant_permissions(
        AsyncSessionLocal,
        user_data["user_id"],
        ["create_feature_flag", "read_feature_flag", "update_feature_flag", "delete_feature_flag"],
    )

    # Clear permissions cache for this user
    if app_cache is not None:
        cache_key = f"perm:user:{user_data['user_id']}"
        await app_cache.delete(cache_key)

    return user_data


@pytest.mark.asyncio
async def test_create_feature_flag_success(test_app):
    """Test creating a feature flag successfully."""
    client, engine, AsyncSessionLocal = test_app

    # Create user with feature flag permissions
    user_data = await create_user_with_ff_permissions(
        AsyncSessionLocal, "ff1", "ff1@example.com", TEST_PASSWORD, client.app.state.cache_client
    )
    tenant_id = user_data["tenant_id"]

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "ff1@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Create feature flag
        create_resp = await http.post(
            "/api/v1/features",
            json={
                "tenant_id": tenant_id,
                "key": "new_feature",
                "name": "New Feature",
                "description": "Test feature",
                "is_enabled": True,
                "enabled_value": {"type": "boolean", "value": True},
                "default_value": {"type": "boolean", "value": False},
            },
            headers=headers,
        )
        assert create_resp.status_code == 200
        data = create_resp.json()
        assert data["key"] == "new_feature"
        assert data["name"] == "New Feature"
        assert data["is_enabled"] is True


@pytest.mark.asyncio
async def test_create_feature_flag_cross_tenant_forbidden(test_app):
    """Test that users cannot create feature flags for other tenants."""
    client, engine, AsyncSessionLocal = test_app

    # Create two tenants with users
    await create_user_with_ff_permissions(
        AsyncSessionLocal, "ff2", "ff2@example.com", TEST_PASSWORD, client.app.state.cache_client
    )
    user2_data = await create_user_with_ff_permissions(
        AsyncSessionLocal, "ff3", "ff3@example.com", TEST_PASSWORD, client.app.state.cache_client
    )
    tenant2_id = user2_data["tenant_id"]

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login as user1
        r = await http.post(
            "/api/v1/auth/login", json={"email": "ff2@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Try to create feature flag for tenant2
        create_resp = await http.post(
            "/api/v1/features",
            json={
                "tenant_id": tenant2_id,
                "key": "malicious_feature",
                "name": "Malicious Feature",
                "is_enabled": True,
            },
            headers=headers,
        )
        assert create_resp.status_code == 403
        assert "different tenant" in create_resp.json()["detail"]


@pytest.mark.asyncio
async def test_evaluate_feature_flag(test_app):
    """Test evaluating a feature flag."""
    client, engine, AsyncSessionLocal = test_app

    # Create user and feature flag
    user_data = await create_user_with_ff_permissions(
        AsyncSessionLocal, "ff4", "ff4@example.com", TEST_PASSWORD, client.app.state.cache_client
    )
    user_data["tenant_id"]

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "ff4@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Create feature flag
        await http.post(
            "/api/v1/features",
            json={
                "key": "test_feature",
                "name": "Test Feature",
                "is_enabled": True,
                "enabled_value": {"value": "enabled"},
            },
            headers=headers,
        )

        # Evaluate feature flag (return enabled status)
        eval_resp = await http.post(
            "/api/v1/features/evaluate", json={"key": "test_feature"}, headers=headers
        )
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert eval_data["key"] == "test_feature"
        assert eval_data["is_enabled"] is True

        # Evaluate feature flag (return value)
        eval_value_resp = await http.post(
            "/api/v1/features/evaluate",
            json={"key": "test_feature", "return_value": True},
            headers=headers,
        )
        assert eval_value_resp.status_code == 200
        eval_value_data = eval_value_resp.json()
        assert eval_value_data["key"] == "test_feature"
        assert eval_value_data["value"] == {"value": "enabled"}


@pytest.mark.asyncio
async def test_update_feature_flag(test_app):
    """Test updating a feature flag."""
    client, engine, AsyncSessionLocal = test_app

    # Create user and feature flag
    await create_user_with_ff_permissions(
        AsyncSessionLocal, "ff5", "ff5@example.com", TEST_PASSWORD, client.app.state.cache_client
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "ff5@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Create feature flag
        create_resp = await http.post(
            "/api/v1/features",
            json={"key": "update_test", "name": "Update Test", "is_enabled": False},
            headers=headers,
        )
        feature_id = create_resp.json()["id"]

        # Update feature flag
        update_resp = await http.put(
            f"/api/v1/features/{feature_id}",
            json={"is_enabled": True, "description": "Updated description"},
            headers=headers,
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["is_enabled"] is True
        assert updated["description"] == "Updated description"


@pytest.mark.asyncio
async def test_delete_feature_flag(test_app):
    """Test deleting a feature flag."""
    client, engine, AsyncSessionLocal = test_app

    # Create user and feature flag
    await create_user_with_ff_permissions(
        AsyncSessionLocal, "ff6", "ff6@example.com", TEST_PASSWORD, client.app.state.cache_client
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "ff6@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Create feature flag
        create_resp = await http.post(
            "/api/v1/features",
            json={"key": "delete_test", "name": "Delete Test", "is_enabled": True},
            headers=headers,
        )
        feature_id = create_resp.json()["id"]

        # Delete feature flag
        delete_resp = await http.delete(f"/api/v1/features/{feature_id}", headers=headers)
        assert delete_resp.status_code == 200
        assert delete_resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_list_feature_flags(test_app):
    """Test listing feature flags."""
    client, engine, AsyncSessionLocal = test_app

    # Create user and multiple feature flags
    user_data = await create_user_with_ff_permissions(
        AsyncSessionLocal, "ff7", "ff7@example.com", TEST_PASSWORD, client.app.state.cache_client
    )
    tenant_id = user_data["tenant_id"]

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "ff7@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Create multiple feature flags
        for i in range(3):
            await http.post(
                "/api/v1/features",
                json={"key": f"list_test_{i}", "name": f"List Test {i}", "is_enabled": i % 2 == 0},
                headers=headers,
            )

        # List all feature flags
        list_resp = await http.get("/api/v1/features", headers=headers)
        assert list_resp.status_code == 200
        features = list_resp.json()
        assert len(features) >= 3
        feature_keys = [f["key"] for f in features]
        assert "list_test_0" in feature_keys
        assert "list_test_1" in feature_keys
        assert "list_test_2" in feature_keys

        # List with tenant filter
        list_tenant_resp = await http.get(
            f"/api/v1/features?tenant_id={tenant_id}", headers=headers
        )
        assert list_tenant_resp.status_code == 200
        tenant_features = list_tenant_resp.json()
        assert len(tenant_features) >= 3


@pytest.mark.asyncio
async def test_evaluate_nonexistent_feature_flag(test_app):
    """Test evaluating a feature flag that doesn't exist."""
    client, engine, AsyncSessionLocal = test_app

    # Create user
    await create_user_with_ff_permissions(
        AsyncSessionLocal, "ff8", "ff8@example.com", TEST_PASSWORD, client.app.state.cache_client
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "ff8@example.com", "password": TEST_PASSWORD}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Evaluate nonexistent feature flag
        eval_resp = await http.post(
            "/api/v1/features/evaluate", json={"key": "nonexistent_feature"}, headers=headers
        )
        # Should return default (disabled) or handle gracefully
        assert eval_resp.status_code in (200, 404)
