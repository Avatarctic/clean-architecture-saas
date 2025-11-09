from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import (
    get_audit_repo,
    get_current_user,
    get_tenant_repo,
    get_tenant_service,
    get_user_repo,
    get_user_service,
    require_any_permission,
    require_permission,
    require_rate_limit,
    require_role_hierarchy_for_user_management,
)
from ..domain.audit import AuditAction, AuditResource, log_audit_event
from ..domain.auth import TokenClaims
from ..domain.tenant import Tenant
from ..exceptions import DuplicateError
from ..logging_config import get_logger
from ..ports.repositories import TenantRepository
from ..schemas.auth import UserResponse, user_to_response
from ..schemas.tenant import TenantCreateRequest, TenantResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


@router.post(
    "/",
    response_model=TenantResponse,
    dependencies=[
        Depends(require_permission("create_tenant")),
        Depends(require_rate_limit),
    ],
)
async def create_tenant(
    req: TenantCreateRequest,
    request: Request,
    tenant_repo: TenantRepository = Depends(get_tenant_repo),
    current_user: TokenClaims = Depends(get_current_user),
    user_repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
):
    logger.info("creating_tenant", extra={"name": req.name, "creator_id": current_user.subject})
    try:
        created = await tenant_repo.create(
            Tenant(
                id=None,
                name=req.name,
                slug=getattr(req, "slug", None),
                domain=getattr(req, "domain", None),
                plan=getattr(req, "plan", "free"),
                status=getattr(req, "status", "active"),
                settings=getattr(req, "settings", None) or {},
            )
        )
        logger.info(
            "tenant_created",
            extra={"tenant_id": created.id, "name": req.name, "slug": created.slug},
        )
    except DuplicateError:
        logger.warning("tenant_creation_failed_duplicate", extra={"name": req.name})
        raise HTTPException(status_code=409, detail="Tenant with that name already exists")

    # Audit log tenant creation
    creator = await user_repo.get_by_id(int(current_user.subject))
    if creator:
        await log_audit_event(
            audit_repo=audit_repo,
            user=creator,
            action=AuditAction.CREATE,
            resource=AuditResource.TENANT,
            details={"name": req.name, "slug": created.slug, "plan": created.plan},
            resource_id=created.id,
            request=request,
        )

    assert created.id is not None
    return TenantResponse(
        id=int(created.id),
        name=created.name,
        slug=created.slug,
        domain=created.domain,
        plan=created.plan,
        status=created.status,
        settings=created.settings,
        created_at=str(created.created_at),
        updated_at=(
            str(created.updated_at) if getattr(created, "updated_at", None) is not None else None
        ),
    )


@router.get(
    "/",
    response_model=List[TenantResponse],
    dependencies=[
        Depends(require_permission("read_all_tenants")),
        Depends(require_rate_limit),
    ],
)
async def list_tenants(tenant_repo: TenantRepository = Depends(get_tenant_repo)):
    logger.info("listing_tenants")
    tenants = await tenant_repo.list_all()
    logger.debug("tenants_listed", extra={"count": len(tenants)})
    out: list[TenantResponse] = []
    for t in tenants:
        assert t.id is not None
        out.append(
            TenantResponse(
                id=int(t.id),
                name=t.name,
                slug=t.slug,
                domain=t.domain,
                plan=t.plan,
                status=t.status,
                settings=t.settings,
                created_at=str(t.created_at),
                updated_at=(
                    str(t.updated_at) if getattr(t, "updated_at", None) is not None else None
                ),
            )
        )
    return out


@router.get(
    "/{id}",
    response_model=TenantResponse,
    dependencies=[
        Depends(require_any_permission("read_own_tenant", "read_all_tenants")),
        Depends(require_rate_limit),
    ],
)
async def get_tenant(
    id: int,
    request: Request,
    tenant_repo: TenantRepository = Depends(get_tenant_repo),
    current_user: TokenClaims = Depends(get_current_user),
):
    """
    Get a single tenant by ID.
    - If user has read_all_tenants permission → can read any tenant (platform admin)
    - If user has read_own_tenant permission → can only read their own tenant
    """
    # Get user permissions from request state (populated by middleware)
    perms = getattr(request.state, "user_permissions", [])

    # Check if user has read_all_tenants permission (platform admin)
    has_read_all = "read_all_tenants" in perms

    if not has_read_all:
        # For read_own_tenant permission, verify accessing own tenant
        current_tenant_id = current_user.tenant_id
        if current_tenant_id is None:
            raise HTTPException(status_code=403, detail="No tenant context")

        if id != current_tenant_id:
            raise HTTPException(status_code=403, detail="Cannot access other tenants")

    logger.info("getting_tenant", extra={"tenant_id": id, "user_id": current_user.subject})
    tenant = await tenant_repo.get_by_id(id)
    if not tenant:
        logger.warning("tenant_not_found", extra={"tenant_id": id, "user_id": current_user.subject})
        raise HTTPException(status_code=404, detail="Tenant not found")

    logger.debug("tenant_retrieved", extra={"tenant_id": id, "tenant_name": tenant.name})
    assert tenant.id is not None
    return TenantResponse(
        id=int(tenant.id),
        name=tenant.name,
        slug=tenant.slug,
        domain=tenant.domain,
        plan=tenant.plan,
        status=tenant.status,
        settings=tenant.settings,
        created_at=str(tenant.created_at),
        updated_at=(
            str(tenant.updated_at) if getattr(tenant, "updated_at", None) is not None else None
        ),
    )


@router.put(
    "/{id}",
    response_model=TenantResponse,
    dependencies=[
        Depends(require_permission("update_tenant")),
        Depends(require_rate_limit),
    ],
)
async def update_tenant(
    id: int,
    payload: dict,
    request: Request,
    tenant_repo: TenantRepository = Depends(get_tenant_repo),
    current_user: TokenClaims = Depends(get_current_user),
    user_repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
):
    """
    Update tenant settings (name, domain, plan, settings).
    Requires update_tenant permission.
    Cannot update status via this endpoint (use /suspend, /activate, /cancel).
    """
    logger.info(
        "updating_tenant",
        extra={"tenant_id": id, "fields": list(payload.keys()), "updater_id": current_user.subject},
    )

    # Prevent status updates via this endpoint
    if "status" in payload:
        logger.warning(
            "tenant_status_update_rejected",
            extra={"tenant_id": id, "updater_id": current_user.subject},
        )
        raise HTTPException(
            status_code=400,
            detail="Cannot update status via this endpoint. Use /suspend, /activate, or /cancel",
        )

    # Get existing tenant
    tenant = await tenant_repo.get_by_id(id)
    if not tenant:
        logger.warning(
            "tenant_not_found_for_update",
            extra={"tenant_id": id, "updater_id": current_user.subject},
        )
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Update tenant
    await tenant_repo.update(id, **payload)

    # Get updated tenant
    updated = await tenant_repo.get_by_id(id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated tenant")

    # Audit log tenant update
    updater = await user_repo.get_by_id(int(current_user.subject))
    if updater:
        await log_audit_event(
            audit_repo=audit_repo,
            user=updater,
            action=AuditAction.UPDATE,
            resource=AuditResource.TENANT,
            details={"tenant_id": id, "fields": list(payload.keys())},
            resource_id=id,
            request=request,
        )

    logger.info("tenant_updated", extra={"tenant_id": id})

    assert updated.id is not None
    return TenantResponse(
        id=int(updated.id),
        name=updated.name,
        slug=updated.slug,
        domain=updated.domain,
        plan=updated.plan,
        status=updated.status,
        settings=updated.settings,
        created_at=str(updated.created_at),
        updated_at=(
            str(updated.updated_at) if getattr(updated, "updated_at", None) is not None else None
        ),
    )


# Status management endpoints: suspend / activate / cancel


@router.post(
    "/{id}/suspend",
    response_model=TenantResponse,
    dependencies=[
        Depends(require_permission("manage_tenant_status")),
        Depends(require_rate_limit),
    ],
)
async def suspend_tenant(
    id: int,
    request: Request,
    tenant_svc=Depends(get_tenant_service),
    current_user: TokenClaims = Depends(get_current_user),
    user_repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
):
    """Suspend a tenant (delegated to service layer)."""
    try:
        updated = await tenant_svc.suspend_tenant(id)
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(e))

    # Audit log tenant suspension
    suspender = await user_repo.get_by_id(int(current_user.subject))
    if suspender:
        await log_audit_event(
            audit_repo=audit_repo,
            user=suspender,
            action=AuditAction.UPDATE,
            resource=AuditResource.TENANT,
            details={"tenant_id": id, "action": "suspend", "tenant_name": updated.name},
            resource_id=id,
            request=request,
        )

    return TenantResponse(
        id=int(updated.id),
        name=updated.name,
        slug=updated.slug,
        domain=updated.domain,
        plan=updated.plan,
        status=updated.status,
        settings=updated.settings,
        created_at=str(updated.created_at),
        updated_at=(
            str(updated.updated_at) if getattr(updated, "updated_at", None) is not None else None
        ),
    )


@router.post(
    "/{id}/activate",
    response_model=TenantResponse,
    dependencies=[
        Depends(require_permission("manage_tenant_status")),
        Depends(require_rate_limit),
    ],
)
async def activate_tenant(
    id: int,
    request: Request,
    tenant_svc=Depends(get_tenant_service),
    current_user: TokenClaims = Depends(get_current_user),
    user_repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
):
    """Activate a tenant (delegated to service layer)."""
    logger.info("activating_tenant", extra={"tenant_id": id, "activator_id": current_user.subject})
    try:
        updated = await tenant_svc.activate_tenant(id)
        logger.info("tenant_activated", extra={"tenant_id": id, "status": updated.status})
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(e))

    # Audit log tenant activation
    activator = await user_repo.get_by_id(int(current_user.subject))
    if activator:
        await log_audit_event(
            audit_repo=audit_repo,
            user=activator,
            action=AuditAction.UPDATE,
            resource=AuditResource.TENANT,
            details={"tenant_id": id, "action": "activate", "tenant_name": updated.name},
            resource_id=id,
            request=request,
        )

    return TenantResponse(
        id=int(updated.id),
        name=updated.name,
        slug=updated.slug,
        domain=updated.domain,
        plan=updated.plan,
        status=updated.status,
        settings=updated.settings,
        created_at=str(updated.created_at),
        updated_at=(
            str(updated.updated_at) if getattr(updated, "updated_at", None) is not None else None
        ),
    )


@router.post(
    "/{id}/cancel",
    response_model=TenantResponse,
    dependencies=[
        Depends(require_permission("manage_tenant_status")),
        Depends(require_rate_limit),
    ],
)
async def cancel_tenant(
    id: int,
    request: Request,
    tenant_svc=Depends(get_tenant_service),
    current_user: TokenClaims = Depends(get_current_user),
    user_repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
):
    """Cancel a tenant (delegated to service layer)."""
    logger.info("cancelling_tenant", extra={"tenant_id": id, "canceller_id": current_user.subject})
    try:
        updated = await tenant_svc.cancel_tenant(id)
        logger.info("tenant_cancelled", extra={"tenant_id": id, "status": updated.status})
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(e))

    # Audit log tenant cancellation
    canceller = await user_repo.get_by_id(int(current_user.subject))
    if canceller:
        await log_audit_event(
            audit_repo=audit_repo,
            user=canceller,
            action=AuditAction.UPDATE,
            resource=AuditResource.TENANT,
            details={"tenant_id": id, "action": "cancel", "tenant_name": updated.name},
            resource_id=id,
            request=request,
        )

    return TenantResponse(
        id=int(updated.id),
        name=updated.name,
        slug=updated.slug,
        domain=updated.domain,
        plan=updated.plan,
        status=updated.status,
        settings=updated.settings,
        created_at=str(updated.created_at),
        updated_at=(
            str(updated.updated_at) if getattr(updated, "updated_at", None) is not None else None
        ),
    )


@router.post(
    "/{id}/users",
    response_model=UserResponse,
    dependencies=[
        Depends(require_any_permission("create_tenant_user", "create_all_users")),
        Depends(require_role_hierarchy_for_user_management()),
        Depends(require_rate_limit),
    ],
)
async def create_user_in_tenant(
    id: int,
    email: str,
    password: str,
    role: str = "member",
    current_user: TokenClaims = Depends(get_current_user),
    user_svc=Depends(get_user_service),
    user_repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
    request: Request = None,  # type: ignore[assignment]
):
    """
    Create a user in the specified tenant.
    - If user has create_all_users permission → can create in any tenant (superadmin)
    - If user has create_tenant_user permission → can only create in their own tenant
    """
    # Get user permissions from request state (populated by middleware)
    perms = getattr(request.state, "user_permissions", [])

    # Check if user has create_all_users permission (superadmin)
    has_create_all = "create_all_users" in perms

    if not has_create_all:
        # For tenant-level permission, verify creating in same tenant
        current_tenant_id = current_user.tenant_id
        if current_tenant_id is None:
            raise HTTPException(status_code=403, detail="No tenant context")

        if id != current_tenant_id:
            raise HTTPException(status_code=403, detail="Cannot create users in other tenants")

    logger.info(
        "creating_user_in_tenant",
        extra={"tenant_id": id, "email": email, "role": role, "creator_id": current_user.subject},
    )
    # Create the user
    created = await user_svc.create_user(int(id), email, password, role=role)
    logger.info(
        "user_created_in_tenant", extra={"tenant_id": id, "user_id": created.id, "email": email}
    )

    # Audit log user creation in tenant
    creator = await user_repo.get_by_id(int(current_user.subject))
    if creator:
        await log_audit_event(
            audit_repo=audit_repo,
            user=creator,
            action=AuditAction.CREATE,
            resource=AuditResource.USER,
            details={"tenant_id": id, "email": email, "role": role, "created_user_id": created.id},
            resource_id=created.id,
            request=request,
        )

    return user_to_response(created)
