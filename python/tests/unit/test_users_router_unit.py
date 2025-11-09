from types import SimpleNamespace

import pytest

from src.app.domain.auth import TokenClaims
from src.app.routers import users as users_router


@pytest.mark.asyncio
async def test_get_user_missing_repo_methods():
    class DummyRepo:
        async def get_by_id(self, id):
            return SimpleNamespace(id=id, tenant_id=1, email="x@example.com", role="member")

    # Mock request with tenant in state and user_permissions
    request = SimpleNamespace(
        state=SimpleNamespace(tenant=SimpleNamespace(id=1), user_permissions=["read_tenant_users"])
    )
    current_user = TokenClaims(
        subject="1",  # Same as user being accessed (allow_self=True)
        tenant_id=1,
    )

    # call the router function directly, passing in a dummy repo
    res = await users_router.get_user(
        1, request=request, current_user=current_user, repo=DummyRepo()
    )
    assert res.email == "x@example.com"


@pytest.mark.asyncio
async def test_list_users_happy_path():
    class DummyRepo:
        async def list_by_tenant(self, tenant_id):
            return [
                SimpleNamespace(id=1, tenant_id=tenant_id, email="a@example.com", role="member")
            ]

    # Mock request with tenant in state
    request = SimpleNamespace(state=SimpleNamespace(tenant=SimpleNamespace(id=1)))
    rows = await users_router.list_users(request=request, repo=DummyRepo(), tenant_id=1)
    assert isinstance(rows, list)
    assert rows[0].email == "a@example.com"
