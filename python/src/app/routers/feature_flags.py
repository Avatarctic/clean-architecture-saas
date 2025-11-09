from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import (
    get_audit_repo,
    get_cache_client,
    get_current_tenant_id,
    get_current_user,
    get_db,
    get_feature_flag_repo,
    get_tenant_repo,
    get_user_repo,
    require_permission,
    require_rate_limit,
)
from ..logging_config import get_logger
from ..schemas.feature_flag import (
    FeatureFlagActionResponse,
    FeatureFlagCreateRequest,
    FeatureFlagEvaluateRequest,
    FeatureFlagEvaluationResponse,
)
from ..services.feature_service import FeatureFlagService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/features", tags=["features"])


@router.post(
    "",
    dependencies=[
        Depends(require_permission("create_feature_flag")),
        Depends(require_rate_limit),
    ],
)
async def create_feature_flag(
    feature_flag: FeatureFlagCreateRequest,
    request: Request,
    current_user=Depends(get_current_user),
    tenant_id: Optional[int] = Depends(get_current_tenant_id),
    feature_flag_repo=Depends(get_feature_flag_repo),
    audit_repo=Depends(get_audit_repo),
    cache=Depends(get_cache_client),
):
    """Create a new feature flag."""
    logger.info(
        "creating_feature_flag",
        extra={"key": feature_flag.key, "tenant_id": tenant_id, "user_id": current_user.subject},
    )
    # Validate tenant ownership - user can only create flags for their own tenant
    requested_tenant_id = feature_flag.tenant_id
    if requested_tenant_id is not None and requested_tenant_id != tenant_id:
        logger.warning(
            "feature_flag_cross_tenant_attempt",
            extra={
                "user_tenant_id": tenant_id,
                "requested_tenant_id": requested_tenant_id,
                "user_id": current_user.subject,
            },
        )
        raise HTTPException(
            status_code=403, detail="cannot create feature flag for a different tenant"
        )

    # Use current tenant if not explicitly provided
    if requested_tenant_id is None:
        requested_tenant_id = tenant_id

    svc = FeatureFlagService(feature_flag_repo, audit=audit_repo, cache=cache)

    try:
        user_id = int(current_user.subject)
    except (ValueError, AttributeError):
        user_id = None

    ff = await svc.create_feature_flag(
        requested_tenant_id,
        feature_flag.key,
        feature_flag.name,
        feature_flag.description,
        feature_flag.is_enabled,
        enabled_value=feature_flag.enabled_value,
        default_value=feature_flag.default_value,
        rules=feature_flag.rules,
        rollout=feature_flag.rollout,
        actor_user={"id": user_id} if user_id is not None else None,
    )
    logger.info(
        "feature_flag_created",
        extra={"flag_id": ff.get("id"), "key": feature_flag.key, "tenant_id": requested_tenant_id},
    )
    return ff


@router.post(
    "/evaluate",
    response_model=FeatureFlagEvaluationResponse,
    dependencies=[
        Depends(require_permission("read_feature_flag")),
        Depends(require_rate_limit),
    ],
)
async def evaluate_feature(
    evaluate_req: FeatureFlagEvaluateRequest,
    request: Request,
    current_user=Depends(get_current_user),
    tenant_id: Optional[int] = Depends(get_current_tenant_id),
    feature_flag_repo=Depends(get_feature_flag_repo),
    cache=Depends(get_cache_client),
    db_session=Depends(get_db),
):
    """Evaluate a feature flag for the current user and context."""
    logger.info(
        "evaluating_feature_flag",
        extra={"key": evaluate_req.key, "tenant_id": tenant_id, "user_id": current_user.subject},
    )
    svc = FeatureFlagService(feature_flag_repo, cache=cache)

    # Use tenant_id from request body if provided, otherwise use current tenant
    eval_tenant_id = evaluate_req.tenant_id if evaluate_req.tenant_id is not None else tenant_id
    user_id = current_user.subject
    custom = evaluate_req.custom or {}

    # Resolve user role
    role = None
    try:
        ur = await get_user_repo(db_session)
        u = await ur.get_by_id(int(user_id))
        if u is not None:
            role = getattr(u, "role", None)
    except Exception:
        role = None

    # Resolve tenant plan
    plan = None
    if eval_tenant_id is not None:
        try:
            tr = await get_tenant_repo(db_session)
            t = await tr.get_by_id(eval_tenant_id)
            if t is not None:
                plan = getattr(t, "plan", None)
        except Exception:
            plan = None

    # Return value or enabled boolean based on request
    if evaluate_req.return_value:
        val = await svc.get_feature_value(
            eval_tenant_id, evaluate_req.key, user_id=user_id, custom=custom, role=role, plan=plan
        )
        logger.debug(
            "feature_flag_value_returned",
            extra={"key": evaluate_req.key, "value": val, "tenant_id": eval_tenant_id},
        )
        return FeatureFlagEvaluationResponse(key=evaluate_req.key, value=val)

    enabled = await svc.is_feature_enabled(
        eval_tenant_id, evaluate_req.key, user_id=user_id, custom=custom, role=role, plan=plan
    )
    logger.debug(
        "feature_flag_evaluated",
        extra={"key": evaluate_req.key, "is_enabled": bool(enabled), "tenant_id": eval_tenant_id},
    )
    return FeatureFlagEvaluationResponse(key=evaluate_req.key, is_enabled=bool(enabled))


@router.put(
    "/{id}",
    dependencies=[
        Depends(require_permission("update_feature_flag")),
        Depends(require_rate_limit),
    ],
)
async def update_feature(
    id: int,
    req: dict,
    feature_flag_repo=Depends(get_feature_flag_repo),
    audit_repo=Depends(get_audit_repo),
    cache=Depends(get_cache_client),
):
    """Update an existing feature flag."""
    logger.info("updating_feature_flag", extra={"flag_id": id, "fields": list(req.keys())})
    svc = FeatureFlagService(feature_flag_repo, audit=audit_repo, cache=cache)
    ff = await svc.update_feature_flag(id, **req)
    logger.info("feature_flag_updated", extra={"flag_id": id, "key": ff.get("key")})
    return ff


@router.delete(
    "/{id}",
    response_model=FeatureFlagActionResponse,
    dependencies=[
        Depends(require_permission("delete_feature_flag")),
        Depends(require_rate_limit),
    ],
)
async def delete_feature(
    id: int,
    feature_flag_repo=Depends(get_feature_flag_repo),
    audit_repo=Depends(get_audit_repo),
    cache=Depends(get_cache_client),
):
    """Delete a feature flag."""
    logger.info("deleting_feature_flag", extra={"flag_id": id})
    svc = FeatureFlagService(feature_flag_repo, audit=audit_repo, cache=cache)
    await svc.delete_feature_flag(id)
    logger.info("feature_flag_deleted", extra={"flag_id": id})
    return FeatureFlagActionResponse(status="ok")


@router.get(
    "",
    dependencies=[
        Depends(require_permission("read_feature_flag")),
        Depends(require_rate_limit),
    ],
)
async def list_features(
    limit: int = 50,
    offset: int = 0,
    tenant_id: Optional[int] = Depends(get_current_tenant_id),
    feature_flag_repo=Depends(get_feature_flag_repo),
):
    """List all feature flags, optionally filtered by tenant."""
    logger.info(
        "listing_feature_flags", extra={"tenant_id": tenant_id, "limit": limit, "offset": offset}
    )
    svc = FeatureFlagService(feature_flag_repo)
    result = await svc.list_feature_flags(tenant_id, limit, offset)
    logger.debug(
        "feature_flags_listed", extra={"count": len(result) if isinstance(result, list) else 0}
    )
    return result
