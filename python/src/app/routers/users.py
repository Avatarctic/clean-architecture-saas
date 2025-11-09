from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import (
    get_audit_repo,
    get_current_tenant_id,
    get_current_user,
    get_session_service,
    get_user_repo,
    get_user_service,
    require_any_permission,
    require_permission,
    require_rate_limit,
    require_role_hierarchy_for_user_management,
)
from ..domain.audit import AuditAction, AuditResource, log_audit_event
from ..domain.auth import TokenClaims
from ..logging_config import get_logger
from ..schemas.auth import UserResponse, user_to_response
from ..schemas.user import (
    ChangePasswordRequest,
    RevokeAllSessionsResponse,
    RevokeSessionResponse,
    UpdateEmailRequest,
    UserActionResponse,
    UserCreateRequest,
)
from ..services.user_service import UserService, pwd_context

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


async def _check_user_access(
    user_id: int,
    current_user: TokenClaims,
    user_repo,
    request: Request,
    allow_self: bool = True,
) -> None:
    """
    Check if current user has access to target user based on:
    1. If target is current user → allowed (if allow_self=True)
    2. If user has *_all_users permission → allowed (superadmin)
    3. If user has *_tenant_users permission AND target is in same tenant → allowed
    4. Otherwise → 403 Forbidden

    Args:
        user_id: Target user ID
        current_user: Current authenticated user (TokenClaims)
        user_repo: User repository
        request: FastAPI request (for checking permissions)
        allow_self: Whether operation on self is allowed (False for delete)
    """
    current_user_id = int(current_user.subject)

    # Check if operating on self
    if user_id == current_user_id:
        if allow_self:
            return  # Operating on self is OK
        else:
            raise HTTPException(status_code=403, detail="Cannot perform this operation on yourself")

    # Get user permissions from request state (populated by middleware)
    perms = getattr(request.state, "user_permissions", [])

    # Check if user has *_all_users or *_all_* permission (superadmin)
    has_all_users_perm = any(
        "all_users" in p or "all_sessions" in p or "all_tenants" in p for p in perms
    )

    if has_all_users_perm:
        return  # Superadmin can access any user

    # For tenant-level permissions, verify target user is in same tenant
    target_user = await user_repo.get_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    current_tenant_id = current_user.tenant_id
    if current_tenant_id is None:
        raise HTTPException(status_code=403, detail="No tenant context")

    if target_user.tenant_id != current_tenant_id:
        raise HTTPException(status_code=403, detail="Cannot access users from other tenants")


@router.get(
    "",
    response_model=List[UserResponse],
    dependencies=[
        Depends(require_permission("read_tenant_users")),
        Depends(require_rate_limit),
    ],
)
async def list_users(
    request: Request,
    repo=Depends(get_user_repo),
    tenant_id: int = Depends(get_current_tenant_id),
):
    # list users for a tenant
    rows = await repo.list_by_tenant(tenant_id)
    return [user_to_response(r) for r in rows]


@router.get(
    "/me",
    response_model=UserResponse,
    dependencies=[
        Depends(require_permission("read_own_profile")),
        Depends(require_rate_limit),
    ],
)
async def get_own_profile(
    current_user=Depends(get_current_user),
    repo=Depends(get_user_repo),
    _rl: None = Depends(require_rate_limit),
):
    # current_user is now TokenClaims
    uid = current_user.subject
    if uid is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    user = await repo.get_by_id(int(uid))
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return user_to_response(user)


@router.post(
    "",
    response_model=UserResponse,
    dependencies=[
        Depends(require_permission("create_tenant_user")),
        Depends(require_role_hierarchy_for_user_management()),
        Depends(require_rate_limit),
    ],
)
async def create_user(
    request: Request,
    user_create: UserCreateRequest,
    user_svc: UserService = Depends(get_user_service),
    tenant_id: int = Depends(get_current_tenant_id),
    audit_repo=Depends(get_audit_repo),
    current_user: TokenClaims = Depends(get_current_user),
    user_repo=Depends(get_user_repo),
):
    logger.info(
        "creating_user",
        extra={
            "email": user_create.email,
            "role": user_create.role,
            "tenant_id": tenant_id,
            "creator_id": current_user.subject,
        },
    )
    # minimal create-user endpoint for tenant admins; uses UserService.create_user
    role = user_create.role or "member"
    created = await user_svc.create_user(
        int(tenant_id), user_create.email, user_create.password, role=role
    )
    logger.info(
        "user_created_successfully",
        extra={"user_id": created.id, "email": user_create.email, "tenant_id": tenant_id},
    )

    # Audit log user creation
    creator = await user_repo.get_by_id(int(current_user.subject))
    if creator:
        await log_audit_event(
            audit_repo=audit_repo,
            user=creator,
            action=AuditAction.CREATE,
            resource=AuditResource.USER,
            details={
                "email": user_create.email,
                "role": user_create.role,
                "created_user_id": created.id,
            },
            resource_id=created.id,
            request=request,
        )

    return user_to_response(created)


@router.get(
    "/{id}",
    response_model=UserResponse,
    dependencies=[
        Depends(require_any_permission("read_tenant_users", "read_all_users")),
        Depends(require_role_hierarchy_for_user_management()),
        Depends(require_rate_limit),
    ],
)
async def get_user(
    id: int,
    request: Request,
    current_user: TokenClaims = Depends(get_current_user),
    repo=Depends(get_user_repo),
):
    """Get user by ID. Validates tenant access unless user has read_all_users permission."""
    await _check_user_access(id, current_user, repo, request, allow_self=True)

    u = await repo.get_by_id(id)
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    return user_to_response(u)


@router.get(
    "/{id}/sessions",
    dependencies=[
        Depends(
            require_any_permission("view_tenant_sessions", "view_all_sessions", "view_own_sessions")
        ),
        Depends(require_role_hierarchy_for_user_management()),
        Depends(require_rate_limit),
    ],
)
async def get_user_sessions(
    id: int,
    request: Request,
    current_user: TokenClaims = Depends(get_current_user),
    repo=Depends(get_user_repo),
    session_svc=Depends(get_session_service),
    _rl: None = Depends(require_rate_limit),
):
    """List all sessions for a user. Validates tenant access unless user has view_all_sessions permission."""
    await _check_user_access(id, current_user, repo, request, allow_self=True)
    logger.info(
        "listing_user_sessions", extra={"user_id": id, "requestor_id": current_user.subject}
    )
    sessions = await session_svc.list_user_sessions(id)
    logger.debug("user_sessions_listed", extra={"user_id": id, "session_count": len(sessions)})
    return sessions


@router.delete(
    "/{id}/sessions/{token_hash}",
    response_model=RevokeSessionResponse,
    dependencies=[
        Depends(
            require_any_permission(
                "terminate_tenant_sessions", "terminate_all_sessions", "terminate_own_sessions"
            )
        ),
        Depends(require_role_hierarchy_for_user_management()),
        Depends(require_rate_limit),
    ],
)
async def delete_user_session(
    id: int,
    token_hash: str,
    request: Request,
    current_user: TokenClaims = Depends(get_current_user),
    repo=Depends(get_user_repo),
    session_svc=Depends(get_session_service),
    _rl: None = Depends(require_rate_limit),
):
    """Revoke a specific session for a user. Validates tenant access unless user has terminate_all_sessions permission."""
    # Note: Don't allow terminating current session via this endpoint (use logout instead)
    # We only check user-level access, not session ownership
    await _check_user_access(id, current_user, repo, request, allow_self=True)

    logger.info(
        "revoking_user_session",
        extra={"user_id": id, "token_hash": token_hash, "requestor_id": current_user.subject},
    )
    success = await session_svc.revoke_user_session(token_hash)
    if not success:
        logger.error("session_revocation_failed", extra={"user_id": id, "token_hash": token_hash})
        raise HTTPException(status_code=500, detail="failed to revoke token")
    logger.info("user_session_revoked", extra={"user_id": id, "token_hash": token_hash})
    return {"revoked": True}


@router.delete(
    "/{id}/sessions",
    response_model=RevokeAllSessionsResponse,
    dependencies=[
        Depends(require_any_permission("terminate_tenant_sessions", "terminate_all_sessions")),
        Depends(require_role_hierarchy_for_user_management()),
        Depends(require_rate_limit),
    ],
)
async def delete_all_user_sessions(
    id: int,
    request: Request,
    current_user: TokenClaims = Depends(get_current_user),
    repo=Depends(get_user_repo),
    session_svc=Depends(get_session_service),
):
    """Revoke all sessions for a user. Validates tenant access unless user has terminate_all_sessions permission."""
    # Allow terminating own sessions (useful for "logout all devices")
    await _check_user_access(id, current_user, repo, request, allow_self=True)

    logger.info(
        "revoking_all_user_sessions", extra={"user_id": id, "requestor_id": current_user.subject}
    )
    try:
        result = await session_svc.revoke_all_user_sessions(id)
        logger.info(
            "all_user_sessions_revoked",
            extra={"user_id": id, "revoked_count": result.get("revoked_count", 0)},
        )
        return {"revoked": True, **result}
    except ValueError as e:
        logger.error("revoke_all_sessions_failed", extra={"user_id": id, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/{id}",
    response_model=UserActionResponse,
    dependencies=[
        Depends(
            require_any_permission("update_own_profile", "update_tenant_users", "update_all_users")
        ),
        Depends(require_role_hierarchy_for_user_management()),
        Depends(require_rate_limit),
    ],
)
async def update_user(
    id: int,
    payload: dict,
    request: Request,
    current_user: TokenClaims = Depends(get_current_user),
    repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
):
    """Update user. Validates tenant access unless user has update_all_users permission."""
    await _check_user_access(id, current_user, repo, request, allow_self=True)
    logger.info(
        "updating_user",
        extra={"user_id": id, "fields": list(payload.keys()), "updater_id": current_user.subject},
    )
    await repo.update(id, **payload)

    # Audit log user update
    updater = await repo.get_by_id(int(current_user.subject))
    if updater:
        await log_audit_event(
            audit_repo=audit_repo,
            user=updater,
            action=AuditAction.UPDATE,
            resource=AuditResource.USER,
            details={"updated_user_id": id, "fields": list(payload.keys())},
            resource_id=id,
            request=request,
        )

    logger.info("user_updated", extra={"user_id": id})
    return UserActionResponse(updated=True)


@router.delete(
    "/{id}",
    response_model=UserActionResponse,
    dependencies=[
        Depends(require_any_permission("delete_tenant_users", "delete_all_users")),
        Depends(require_role_hierarchy_for_user_management()),
        Depends(require_rate_limit),
    ],
)
async def delete_user(
    id: int,
    request: Request,
    current_user: TokenClaims = Depends(get_current_user),
    repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
    _rl: None = Depends(require_rate_limit),
):
    """Delete user. Cannot delete yourself. Validates tenant access unless user has delete_all_users permission."""
    logger.info("deleting_user", extra={"user_id": id, "deleter_id": current_user.subject})
    await _check_user_access(id, current_user, repo, request, allow_self=False)

    # Get user info before deletion for audit log
    deleted_user = await repo.get_by_id(id)
    deleted_email = getattr(deleted_user, "email", None) if deleted_user else None

    await repo.delete(id)
    logger.info("user_deleted", extra={"user_id": id, "email": deleted_email})

    # Audit log user deletion
    deleter = await repo.get_by_id(int(current_user.subject))
    if deleter:
        await log_audit_event(
            audit_repo=audit_repo,
            user=deleter,
            action=AuditAction.DELETE,
            resource=AuditResource.USER,
            details={"deleted_user_id": id, "deleted_email": deleted_email},
            resource_id=id,
            request=request,
        )

    return UserActionResponse(deleted=True)


@router.post(
    "/{id}/password",
    response_model=UserActionResponse,
    dependencies=[
        Depends(
            require_any_permission(
                "change_own_password", "change_tenant_user_password", "change_user_password"
            )
        ),
        Depends(require_role_hierarchy_for_user_management()),
        Depends(require_rate_limit),
    ],
)
async def change_user_password(
    id: int,
    password_change: ChangePasswordRequest,
    request: Request,
    current_user: TokenClaims = Depends(get_current_user),
    repo=Depends(get_user_repo),
    user_svc: UserService = Depends(get_user_service),
    audit_repo=Depends(get_audit_repo),
    _rl: None = Depends(require_rate_limit),
):
    """Change user password. Validates tenant access unless user has change_user_password permission."""
    await _check_user_access(id, current_user, repo, request, allow_self=True)

    logger.info("changing_user_password", extra={"user_id": id, "changer_id": current_user.subject})
    hashed = pwd_context.hash(password_change.new_password)
    await user_svc.user_repo.set_password(id, hashed)

    # Audit log password change
    changer = await repo.get_by_id(int(current_user.subject))
    if changer:
        is_self = int(current_user.subject) == id
        await log_audit_event(
            audit_repo=audit_repo,
            user=changer,
            action=AuditAction.UPDATE,
            resource=AuditResource.USER,
            details={"target_user_id": id, "action": "password_change", "self": is_self},
            resource_id=id,
            request=request,
        )

    logger.info(
        "user_password_changed", extra={"user_id": id, "is_self": int(current_user.subject) == id}
    )
    return UserActionResponse(changed=True)


@router.patch(
    "/{id}/email",
    response_model=UserActionResponse,
    dependencies=[
        Depends(
            require_any_permission(
                "update_own_email", "update_tenant_user_email", "update_user_email"
            )
        ),
        Depends(require_role_hierarchy_for_user_management()),
        Depends(require_rate_limit),
    ],
)
async def patch_user_email(
    id: int,
    email_update: UpdateEmailRequest,
    request: Request,
    current_user: TokenClaims = Depends(get_current_user),
    repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
    _rl: None = Depends(require_rate_limit),
):
    """Update user email. Validates tenant access unless user has update_user_email permission."""
    await _check_user_access(id, current_user, repo, request, allow_self=True)

    logger.info(
        "updating_user_email",
        extra={
            "user_id": id,
            "new_email": email_update.new_email,
            "updater_id": current_user.subject,
        },
    )
    # Get old email for audit
    target_user = await repo.get_by_id(id)
    old_email = getattr(target_user, "email", None) if target_user else None

    await repo.set_email(id, email_update.new_email)

    # Audit log email update
    updater = await repo.get_by_id(int(current_user.subject))
    if updater:
        await log_audit_event(
            audit_repo=audit_repo,
            user=updater,
            action=AuditAction.UPDATE,
            resource=AuditResource.USER,
            details={
                "target_user_id": id,
                "action": "email_change",
                "old_email": old_email,
                "new_email": email_update.new_email,
            },
            resource_id=id,
            request=request,
        )

    logger.info("user_email_updated", extra={"user_id": id})
    return UserActionResponse(updated=True)
