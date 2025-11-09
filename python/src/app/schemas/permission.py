from typing import Dict, List, Optional

from pydantic import BaseModel


class PermissionResponse(BaseModel):
    """Response model for a single permission."""

    id: int
    name: str
    description: Optional[str] = None


class RoleResponse(BaseModel):
    """Response model for a role."""

    id: int
    name: str
    description: Optional[str] = None


class RolePermissionsResponse(BaseModel):
    """Response model for role permissions."""

    role: str
    permissions: List[str]


class AvailablePermissionsResponse(BaseModel):
    """Response model for listing all available permissions."""

    permissions: List[dict]
    categorized_permissions: Dict[str, List[dict]]


class SetRolePermissionsRequest(BaseModel):
    """Request model for setting permissions for a role."""

    permissions: List[str]


class AssignPermissionRequest(BaseModel):
    """Request model for assigning a single permission to a role."""

    role_id: int
    permission_id: int


class RemovePermissionRequest(BaseModel):
    """Request model for removing a permission from a role."""

    role_id: int
    permission_id: int


class PermissionActionResponse(BaseModel):
    """Generic response for permission actions."""

    success: bool
    message: Optional[str] = None
