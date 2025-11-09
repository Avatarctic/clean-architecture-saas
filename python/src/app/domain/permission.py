from dataclasses import dataclass
from typing import List, Protocol


@dataclass
class Permission:
    name: str
    description: str | None = None


class RolePermissionPort(Protocol):
    async def get_role_permissions(self, role: str) -> List[str]: ...

    async def list_user_permissions(self, user_id: int) -> List[str]: ...


class PermissionEvaluator:
    """Evaluate permissions for a user given a role.
    This encapsulates the simple role->permission mapping logic.
    """

    def __init__(self, port: RolePermissionPort):
        self.port = port

    async def evaluate_for_role(self, role: str) -> List[str]:
        if not role:
            return []
        perms = await self.port.get_role_permissions(role)
        return perms

    async def evaluate_for_user(self, user_id: int) -> List[str]:
        """Evaluate effective permissions for a user.

        Delegates to the port which handles user→role→permissions lookup.
        Let exceptions surface to caller (fail-fast).
        """
        return await self.port.list_user_permissions(user_id)
