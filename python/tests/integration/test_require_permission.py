import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import TEST_PASSWORD

# test_app fixture provides the test client; create_test_app import not needed


@pytest.mark.anyio
async def test_protected_route_forbidden(test_app, monkeypatch):
    client, engine, AsyncSessionLocal = test_app

    # Middleware automatically denies without proper authentication
    # No need to mock AccessControlService

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://test"
    ) as aclient:
        # no auth header -> will be rejected by token verification before permission check
        resp = await aclient.get("/api/v1/protected/secret")
        assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_protected_route_allowed(test_app, monkeypatch):
    client, engine, AsyncSessionLocal = test_app

    # Create a user with the view_secret permission by creating user with appropriate role
    from tests.conftest import create_tenant_and_user_direct

    await create_tenant_and_user_direct(
        AsyncSessionLocal,
        tenant_name="perm_test",
        email="permtest@example.com",
        password=TEST_PASSWORD,
        role="admin",  # admin role should have view_secret permission
    )

    # Login to get real token
    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://test"
    ) as aclient:
        # First login
        login_resp = await aclient.post(
            "/api/v1/auth/login", json={"email": "permtest@example.com", "password": TEST_PASSWORD}
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Mock permission repository to return view_secret permission
        from src.app.infrastructure.repositories import get_repositories

        original_get_repositories = get_repositories

        def mock_get_repositories(session, cache=None):
            repos = original_get_repositories(session, cache)

            original_perms_repo = repos["permissions"]

            class MockPermissionsRepo:
                async def list_user_permissions(self, user_id: int):
                    return ["view_secret"]

                def __getattr__(self, name):
                    return getattr(original_perms_repo, name)

            repos["permissions"] = MockPermissionsRepo()
            return repos

        import src.app.infrastructure.repositories as repos_module

        repos_module.get_repositories = mock_get_repositories

        try:
            # Now access protected route with real authentication
            headers = {"Authorization": f"Bearer {token}"}
            resp = await aclient.get("/api/v1/protected/secret", headers=headers)
            # Should succeed with the mocked permission
            assert resp.status_code == 200
        finally:
            repos_module.get_repositories = original_get_repositories
