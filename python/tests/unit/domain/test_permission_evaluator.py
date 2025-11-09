import asyncio

import pytest

from src.app.domain.permission import PermissionEvaluator


class DummyPort:
    def __init__(self, perms_map):
        self.perms_map = perms_map

    async def get_role_permissions(self, role: str):
        # simulate async
        await asyncio.sleep(0)
        return self.perms_map.get(role, [])


@pytest.mark.asyncio
async def test_evaluate_for_role_returns_permissions():
    port = DummyPort({"admin": ["read", "write"], "member": ["read"]})
    ev = PermissionEvaluator(port)
    perms = await ev.evaluate_for_role("admin")
    assert perms == ["read", "write"]


@pytest.mark.asyncio
async def test_evaluate_for_role_handles_empty_role():
    port = DummyPort({"admin": ["read", "write"]})
    ev = PermissionEvaluator(port)
    perms = await ev.evaluate_for_role("")
    assert perms == []
