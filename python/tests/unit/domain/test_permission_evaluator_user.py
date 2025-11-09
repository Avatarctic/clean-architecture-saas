import asyncio

import pytest

from src.app.domain.permission import PermissionEvaluator


class DummyPort:
    """Test port that implements user->role->permissions lookup."""

    def __init__(self, users_map, role_map):
        self.users_map = users_map
        self.role_map = role_map

    async def get_role_permissions(self, role: str):
        await asyncio.sleep(0)
        return self.role_map.get(role, [])

    async def list_user_permissions(self, user_id: int):
        """Simulates repository behavior: lookup user, get role, return permissions."""
        await asyncio.sleep(0)
        user = self.users_map.get(user_id)
        if user is None:
            return []
        role = getattr(user, "role", None)
        if role is None:
            return []
        return self.role_map.get(role, [])


@pytest.mark.asyncio
async def test_evaluate_for_user_prefers_user_permissions():
    """Test that evaluator correctly delegates to list_user_permissions."""

    class U:
        def __init__(self, role):
            self.role = role

    users = {1: U("admin")}
    roles = {"admin": ["read", "write"]}
    port = DummyPort(users, roles)
    ev = PermissionEvaluator(port)
    perms = await ev.evaluate_for_user(1)
    assert perms == ["read", "write"]


@pytest.mark.asyncio
async def test_evaluate_for_user_falls_back_to_role():
    """Test that evaluator returns role-based permissions when user exists."""

    class U:
        def __init__(self, role):
            self.role = role

    users = {2: U("member")}
    roles = {"member": ["read"]}
    port = DummyPort(users, roles)
    ev = PermissionEvaluator(port)
    perms = await ev.evaluate_for_user(2)
    assert perms == ["read"]
