"""Integration tests for email verification and email update flows."""

import pytest
from httpx import ASGITransport, AsyncClient


def create_email_token_service(cache):
    """Helper to create EmailTokenService with proper repository using the app's cache."""
    from src.app.infrastructure.repositories.email_token_cache_repository import (
        EmailTokenCacheRepository,
    )
    from src.app.services.email_token_service import EmailTokenService

    email_token_repo = EmailTokenCacheRepository(cache)
    return EmailTokenService(email_token_repo)


async def create_user_with_email_perms(
    AsyncSessionLocal, tenant_name, email, password, app_cache=None
):
    """Helper to create a user with permissions (for email tests, minimal perms needed)."""
    from src.app.infrastructure.repositories import get_repositories
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, tenant_name, email, password, "member"
    )

    # Grant minimal permissions (email operations don't need special perms, just auth)
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        permissions_repo = repos["permissions"]
        user_repo = repos["users"]

        user = await user_repo.get_by_id(user_data["user_id"])
        user_role = getattr(user, "role", "member")

        await permissions_repo.set_role_permissions(user_role, ["read_own_profile"])
        await session.commit()

    # Clear permissions cache
    if app_cache is not None:
        cache_key = f"perm:user:{user_data['user_id']}"
        await app_cache.delete(cache_key)

    return user_data


@pytest.mark.asyncio
async def test_verify_email_with_token(test_app):
    """Test verifying email with a valid token."""
    client, engine, AsyncSessionLocal = test_app
    cache = client.app.state.cache_client
    cache = client.app.state.cache_client

    # Create user
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "ev1", "ev1@example.com", "pass", "member"
    )
    user_id = user_data["user_id"]

    # Generate verification token
    token_service = create_email_token_service(cache)
    token = await token_service.create_email_verification_token(user_id, "ev1@example.com")

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Verify email with token (GET method)
        verify_resp = await http.get(f"/api/v1/auth/verify-email?token={token}")
        # Should redirect or return success
        assert verify_resp.status_code in (200, 302, 307)


@pytest.mark.asyncio
async def test_verify_email_with_invalid_token(test_app):
    """Test verifying email with an invalid token."""
    client, engine, AsyncSessionLocal = test_app

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Try to verify with invalid token
        verify_resp = await http.get("/api/v1/auth/verify-email?token=invalid_token_xyz")
        # Should return error
        assert verify_resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_verify_email_post_method(test_app):
    """Test verifying email using POST method."""
    client, engine, AsyncSessionLocal = test_app
    cache = client.app.state.cache_client

    # Create user and token
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "ev2", "ev2@example.com", "pass", "member"
    )
    user_id = user_data["user_id"]

    token_service = create_email_token_service(cache)
    token = await token_service.create_email_verification_token(user_id, "ev2@example.com")

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Verify email with POST
        verify_resp = await http.post("/api/v1/auth/verify-email", json={"token": token})
        assert verify_resp.status_code in (200, 302, 307)


@pytest.mark.asyncio
async def test_resend_verification_email(test_app):
    """Test resending verification email."""
    client, engine, AsyncSessionLocal = test_app

    # Create user
    from tests.conftest import create_tenant_and_user_direct

    await create_tenant_and_user_direct(
        AsyncSessionLocal, "ev3", "ev3@example.com", "pass", "member"
    )

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Login
        r = await http.post(
            "/api/v1/auth/login", json={"email": "ev3@example.com", "password": "pass"}
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Resend verification
        resend_resp = await http.post("/api/v1/auth/resend-verification", headers=headers)
        # Should succeed (even if email sending is mocked)
        assert resend_resp.status_code == 200


@pytest.mark.asyncio
async def test_resend_verification_without_auth_fails(test_app):
    """Test that resending verification without auth and without email fails."""
    client, engine, AsyncSessionLocal = test_app

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Try to resend without auth and without email in body
        resend_resp = await http.post("/api/v1/auth/resend-verification")
        # Should return 400 because email is required
        assert resend_resp.status_code == 400
        assert "email" in resend_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_confirm_email_update_with_token(test_app):
    """Test confirming email update with valid token."""
    client, engine, AsyncSessionLocal = test_app
    cache = client.app.state.cache_client

    # Create user
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "ev4", "ev4@example.com", "pass", "member"
    )
    user_id = user_data["user_id"]

    # Generate email update token
    token_service = create_email_token_service(cache)
    token = await token_service.create_email_update_token(user_id, "ev4_new@example.com")

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Confirm email update with GET
        confirm_resp = await http.get(f"/api/v1/auth/confirm-email-update?token={token}")
        # Should redirect or return success
        assert confirm_resp.status_code in (200, 302, 307)


@pytest.mark.asyncio
async def test_confirm_email_update_post_method(test_app):
    """Test confirming email update using POST method."""
    client, engine, AsyncSessionLocal = test_app
    cache = client.app.state.cache_client

    # Create user and token
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "ev5", "ev5@example.com", "pass", "member"
    )
    user_id = user_data["user_id"]

    token_service = create_email_token_service(cache)
    token = await token_service.create_email_update_token(user_id, "ev5_new@example.com")

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Confirm with POST
        confirm_resp = await http.post("/api/v1/auth/confirm-email-update", json={"token": token})
        assert confirm_resp.status_code in (200, 302, 307)


@pytest.mark.asyncio
async def test_confirm_email_update_with_invalid_token(test_app):
    """Test confirming email update with invalid token fails."""
    client, engine, AsyncSessionLocal = test_app

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Try to confirm with invalid token
        confirm_resp = await http.get("/api/v1/auth/confirm-email-update?token=invalid_token")
        assert confirm_resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_email_token_expiration(test_app):
    """Test that expired email tokens are rejected."""
    client, engine, AsyncSessionLocal = test_app
    cache = client.app.state.cache_client

    # Create user
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "ev6", "ev6@example.com", "pass", "member"
    )
    user_id = user_data["user_id"]

    # Generate token with very short TTL
    token_service = create_email_token_service(cache)
    token = await token_service.create_email_verification_token(
        user_id, "ev6@example.com", ttl=1  # 1 second TTL
    )

    # Wait for token to expire
    import asyncio

    await asyncio.sleep(2)

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Try to verify with expired token
        verify_resp = await http.get(f"/api/v1/auth/verify-email?token={token}")
        # Should fail
        assert verify_resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_email_token_cannot_be_reused(test_app):
    """Test that email tokens can only be used once."""
    client, engine, AsyncSessionLocal = test_app
    cache = client.app.state.cache_client

    # Create user
    from tests.conftest import create_tenant_and_user_direct

    user_data = await create_tenant_and_user_direct(
        AsyncSessionLocal, "ev7", "ev7@example.com", "pass", "member"
    )
    user_id = user_data["user_id"]

    # Generate token
    token_service = create_email_token_service(cache)
    token = await token_service.create_email_verification_token(user_id, "ev7@example.com")

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Use token once
        first_resp = await http.get(f"/api/v1/auth/verify-email?token={token}")
        assert first_resp.status_code in (200, 302, 307)

        # Try to use token again
        second_resp = await http.get(f"/api/v1/auth/verify-email?token={token}")
        # Should fail (token consumed)
        assert second_resp.status_code in (400, 404)
