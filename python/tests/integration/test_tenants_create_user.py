from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_create_user_in_tenant_returns_userresponse(monkeypatch, test_app):
    client, engine, AsyncSessionLocal = test_app

    # monkeypatch user service to return a SimpleNamespace user
    class DummyUserService:
        async def create_user(self, tenant_id, email, password, role="member"):
            return SimpleNamespace(
                id=7,
                tenant_id=tenant_id,
                email=email,
                first_name="F",
                last_name="L",
                role=role,
                is_active=True,
                email_verified=False,
                audit_enabled=False,
                last_login_at=None,
                created_at=None,
                updated_at=None,
            )

    monkeypatch.setattr("src.app.routers.tenants.get_user_service", lambda: DummyUserService())
    # override any auth/role dependencies on the route so test can call handler directly
    from fastapi.routing import APIRoute

    def _allow(*args, **kwargs):
        return True

    for r in client.app.routes:
        if getattr(r, "path", "") == "/api/v1/tenants/{id}/users" and isinstance(r, APIRoute):
            for dep in getattr(r.dependant, "dependencies", []) or []:
                call = getattr(dep, "call", None)
                if callable(call):
                    client.app.dependency_overrides[call] = _allow
            break
    # Call the router function directly to validate the mapping and response shape.
    from src.app.domain.auth import TokenClaims
    from src.app.routers import tenants as tenants_router

    # Create mock request with required state attributes
    mock_request = SimpleNamespace(
        state=SimpleNamespace(tenant=SimpleNamespace(id=1), user_permissions=["create_tenant_user"])
    )

    # Create mock current_user
    mock_current_user = TokenClaims(
        subject="1",
        tenant_id=1,
    )

    # Create mock repositories
    class DummyUserRepo:
        async def get_by_id(self, user_id):
            return SimpleNamespace(
                id=user_id,
                tenant_id=1,
                email="creator@example.com",
                first_name="Creator",
                last_name="User",
                role="admin",
            )

    class DummyAuditRepo:
        async def create(self, **kwargs):
            return SimpleNamespace(id=1, **kwargs)

    created = await tenants_router.create_user_in_tenant(
        1,
        "new@example.com",
        TEST_PASSWORD,
        role="member",
        request=mock_request,
        current_user=mock_current_user,
        user_svc=DummyUserService(),
        user_repo=DummyUserRepo(),
        audit_repo=DummyAuditRepo(),
    )
    # created is a Pydantic model (UserResponse) or object convertible to dict
    data = created.dict() if hasattr(created, "dict") else created
    assert int(data["id"]) == 7
    assert data["email"] == "new@example.com"
    assert int(data["tenant_id"]) == 1


@pytest.mark.asyncio
async def test_users_endpoints_permission_failures(test_app):
    client, engine, AsyncSessionLocal = test_app
    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        r = await http.get("/api/v1/users?tenant_id=1")
        assert r.status_code in (401, 403)
        r2 = await http.post(
            "/api/v1/users", json={"tenant_id": 1, "email": "e@e.com", "password": TEST_PASSWORD}
        )
        assert r2.status_code in (401, 403)
