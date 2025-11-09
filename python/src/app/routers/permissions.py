from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import (
    get_audit_repo,
    get_current_user,
    get_permission_repo,
    get_user_repo,
    require_permission,
    require_rate_limit,
)
from ..domain.audit import AuditAction, AuditResource, log_audit_event
from ..domain.auth import TokenClaims
from ..logging_config import get_logger
from ..ports.repositories import RolePermissionRepository
from ..schemas.permission import (
    AvailablePermissionsResponse,
    PermissionActionResponse,
    RolePermissionsResponse,
    SetRolePermissionsRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/permissions", tags=["permissions"])


@router.get(
    "",
    response_model=AvailablePermissionsResponse,
    dependencies=[
        Depends(require_permission("view_permissions")),
        Depends(require_rate_limit),
    ],
)
async def get_available_permissions(
    repo: RolePermissionRepository = Depends(get_permission_repo),
):
    """
    Get all available permissions in the system, organized by category.
    """
    all_permissions = await repo.list_permissions()

    # Categorize permissions
    categorized: dict[str, list] = {
        "user_management": [],
        "session_management": [],
        "tenant_management": [],
        "feature_flags": [],
        "permission_management": [],
        "audit_monitoring": [],
    }

    for perm in all_permissions:
        name = perm.get("name", "")
        if any(x in name for x in ["user", "profile", "password", "email"]):
            categorized["user_management"].append(perm)
        elif "session" in name:
            categorized["session_management"].append(perm)
        elif "tenant" in name:
            categorized["tenant_management"].append(perm)
        elif "feature" in name:
            categorized["feature_flags"].append(perm)
        elif "permission" in name or "role" in name:
            categorized["permission_management"].append(perm)
        elif "audit" in name:
            categorized["audit_monitoring"].append(perm)

    return AvailablePermissionsResponse(
        permissions=all_permissions,
        categorized_permissions=categorized,
    )


@router.get(
    "/roles/{role}",
    response_model=RolePermissionsResponse,
    dependencies=[
        Depends(require_permission("view_permissions")),
        Depends(require_rate_limit),
    ],
)
async def get_role_permissions(
    role: str,
    repo: RolePermissionRepository = Depends(get_permission_repo),
):
    """
    Get all permissions assigned to a specific role.
    """
    role_obj = await repo.get_role_by_name(role)
    if not role_obj:
        raise HTTPException(status_code=404, detail="role not found")

    permissions = await repo.list_role_permissions(role_obj.id)

    return RolePermissionsResponse(
        role=role,
        permissions=[str(p.get("name", "")) for p in permissions],
    )


@router.put(
    "/roles/{role}",
    response_model=PermissionActionResponse,
    dependencies=[
        Depends(require_permission("manage_permissions")),
        Depends(require_rate_limit),
    ],
)
async def set_role_permissions(
    role: str,
    permissions_req: SetRolePermissionsRequest,
    request: Request,
    repo: RolePermissionRepository = Depends(get_permission_repo),
    current_user: TokenClaims = Depends(get_current_user),
    user_repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
):
    """
    Set all permissions for a role (replaces existing permissions).
    """
    logger.info(
        "setting_role_permissions",
        extra={
            "role": role,
            "permission_count": len(permissions_req.permissions),
            "user_id": current_user.subject,
        },
    )
    # Ensure role exists
    role_obj = await repo.get_role_by_name(role)
    if not role_obj:
        # Create role if it doesn't exist
        logger.info("creating_role", extra={"role": role})
        role_obj = await repo.create_role(role, None)

    # Bulk fetch all permissions by names (1 query instead of N)
    permission_objects = await repo.get_permissions_by_names(permissions_req.permissions)
    permission_ids = [p["id"] for p in permission_objects]

    # Clear existing permissions and set new ones in bulk (2 queries instead of N+1)
    role_id = role_obj.id if hasattr(role_obj, "id") else role_obj.get("id")
    await repo.clear_role_permissions(role_id)
    await repo.bulk_assign_permissions_to_role(role_id, permission_ids)

    logger.info(
        "role_permissions_updated", extra={"role": role, "permission_count": len(permission_ids)}
    )

    # Audit log permission update
    updater = await user_repo.get_by_id(int(current_user.subject))
    if updater:
        await log_audit_event(
            audit_repo=audit_repo,
            user=updater,
            action=AuditAction.UPDATE,
            resource=AuditResource.PERMISSION,
            details={"role": role, "permissions": permissions_req.permissions, "action": "set_all"},
            resource_id=role_id,
            request=request,
        )

    return PermissionActionResponse(
        success=True,
        message="permissions updated successfully",
    )


@router.post(
    "/roles/{role}/permissions",
    response_model=PermissionActionResponse,
    dependencies=[
        Depends(require_permission("manage_permissions")),
        Depends(require_rate_limit),
    ],
)
async def add_permission_to_role(
    role: str,
    permission: str,
    request: Request,
    repo: RolePermissionRepository = Depends(get_permission_repo),
    current_user: TokenClaims = Depends(get_current_user),
    user_repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
):
    """
    Add a single permission to a role.
    """
    logger.info(
        "adding_permission_to_role",
        extra={"role": role, "permission": permission, "user_id": current_user.subject},
    )
    # Ensure role exists
    role_obj = await repo.get_role_by_name(role)
    if not role_obj:
        role_obj = await repo.create_role(role, None)

    # Ensure permission exists - do NOT auto-create to prevent typos
    perm = await repo.get_permission_by_name(permission)
    if not perm:
        logger.warning("permission_not_found", extra={"permission": permission, "role": role})
        raise HTTPException(
            status_code=404, detail=f"permission '{permission}' not found in system"
        )

    # Assign permission to role
    role_id = role_obj.id if hasattr(role_obj, "id") else role_obj.get("id")
    perm_id = perm.id if hasattr(perm, "id") else perm.get("id")
    await repo.assign_permission_to_role(role_id, perm_id)

    logger.info("permission_added_to_role", extra={"role": role, "permission": permission})

    # Audit log permission addition
    adder = await user_repo.get_by_id(int(current_user.subject))
    if adder:
        await log_audit_event(
            audit_repo=audit_repo,
            user=adder,
            action=AuditAction.CREATE,
            resource=AuditResource.PERMISSION,
            details={"role": role, "permission": permission, "action": "add_permission"},
            resource_id=role_id,
            request=request,
        )

    return PermissionActionResponse(
        success=True, message=f"Permission '{permission}' added to role '{role}'"
    )


@router.delete(
    "/roles/{role}/permissions/{permission}",
    response_model=PermissionActionResponse,
    dependencies=[
        Depends(require_permission("manage_permissions")),
        Depends(require_rate_limit),
    ],
)
async def remove_permission_from_role(
    role: str,
    permission: str,
    request: Request,
    repo: RolePermissionRepository = Depends(get_permission_repo),
    current_user: TokenClaims = Depends(get_current_user),
    user_repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
):
    """
    Remove a single permission from a role.
    """
    logger.info(
        "removing_permission_from_role",
        extra={"role": role, "permission": permission, "user_id": current_user.subject},
    )
    role_obj = await repo.get_role_by_name(role)
    if not role_obj:
        logger.warning("role_not_found_for_permission_removal", extra={"role": role})
        raise HTTPException(status_code=404, detail="role not found")

    perm = await repo.get_permission_by_name(permission)
    if not perm:
        logger.warning(
            "permission_not_found_for_removal", extra={"permission": permission, "role": role}
        )
        raise HTTPException(status_code=404, detail="permission not found")

    role_id = role_obj.id if hasattr(role_obj, "id") else role_obj.get("id")
    perm_id = perm.id if hasattr(perm, "id") else perm.get("id")
    await repo.remove_permission_from_role(role_id, perm_id)

    logger.info("permission_removed_from_role", extra={"role": role, "permission": permission})

    # Audit log permission removal
    remover = await user_repo.get_by_id(int(current_user.subject))
    if remover:
        await log_audit_event(
            audit_repo=audit_repo,
            user=remover,
            action=AuditAction.DELETE,
            resource=AuditResource.PERMISSION,
            details={"role": role, "permission": permission, "action": "remove_permission"},
            resource_id=role_id,
            request=request,
        )

    return PermissionActionResponse(
        success=True, message=f"Permission '{permission}' removed from role '{role}'"
    )
