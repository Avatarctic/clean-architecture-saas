"""Authorization decorators and rate limiting for FastAPI endpoints.

This module provides dependency factories for:
- Permission-based access control (RBAC)
- Role hierarchy enforcement
- Rate limiting per tenant
"""

from typing import Any, Dict

from fastapi import Depends, HTTPException, Request
from starlette import status

from ..domain.auth import TokenClaims
from ..ports.repositories import TenantRepository, UserRepository
from .injection import get_current_user, get_tenant_repo, get_user_repo
from .providers import get_cache_client


async def require_rate_limit(
    request: Request,
    tenant_repo: TenantRepository = Depends(get_tenant_repo),
    cache: Any = Depends(get_cache_client),
) -> None:
    """Dependency enforcing rate limits per-tenant (fallback to defaults).

    Uses pre-resolved tenant from request.state.tenant (set by middleware).
    Reads tenant.settings['rate_limit'] = {"calls": int, "period": int}.
    Falls back to defaults calls=10, period=60.
    """
    ip = request.client.host if request.client else "unknown"

    # Use pre-resolved tenant from middleware
    tenant = getattr(request.state, "tenant", None)

    # read per-tenant rate limit from tenant.settings if present
    rl: Dict[str, Any] = {}
    if tenant and getattr(tenant, "settings", None):
        try:
            s = tenant.settings
            if isinstance(s, dict):
                rl = s.get("rate_limit", {}) or {}
        except Exception as e:
            try:
                logger = __import__("structlog").get_logger(__name__)
                logger.debug(
                    "tenant_settings_read_failed",
                    extra={"tenant_id": getattr(tenant, "id", None), "error": str(e)},
                )
            except Exception:
                # swallow logging failures
                pass
            rl = {}

    calls = int(rl.get("calls", 10))
    period = int(rl.get("period", 60))

    # allow test harness to set a cache on the FastAPI app state which should take precedence
    try:
        cache = getattr(request.app.state, "cache_client", None) or cache
    except Exception as e:
        try:
            logger = __import__("structlog").get_logger(__name__)
            logger.debug("request_app_state_cache_read_failed", error=str(e))
        except Exception:
            # swallow logging failures
            pass

    key = f"rl:tenant:{tenant.id if tenant else 'global'}:{ip}:{request.url.path}"

    # Atomic rate limiting pattern:
    # 1. Try to increment - this creates key if it doesn't exist
    # 2. If count is 1, the key was just created - set TTL
    # 3. Race condition window is minimal since we check immediately after incr
    try:
        count = await cache.incr(key)
        if count == 1:
            # Key was just created by this incr, set TTL immediately
            # Small race window exists but is acceptable for rate limiting
            await cache.expire(key, period)
    except Exception:
        # If cache operation fails, allow the request (fail-open for availability)
        count = 0

    if count > calls:
        # Record rate limit hit
        try:
            from ..metrics import RATE_LIMIT_HITS

            tenant_id = str(tenant.id) if tenant else "global"
            if RATE_LIMIT_HITS is not None:
                RATE_LIMIT_HITS.labels(tenant_id=tenant_id).inc()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )


def require_permission(permission_name: str):
    """Dependency that ensures the current user has the specified permission.

    Uses pre-fetched permissions from request.state.user_permissions (populated
    by CurrentUserMiddleware) to avoid repeated DB/cache queries.
    """

    async def dependency(
        request: Request,
        current_user=Depends(get_current_user),
    ):
        if current_user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Use pre-fetched permissions from middleware
        perms = getattr(request.state, "user_permissions", [])

        # Record permission check metric
        try:
            from ..metrics import PERMISSION_CHECKS

            result = "granted" if permission_name in perms else "denied"
            if PERMISSION_CHECKS is not None:
                PERMISSION_CHECKS.labels(permission=permission_name, result=result).inc()
        except Exception:
            pass  # Don't fail auth on metrics errors

        if permission_name not in perms:
            raise HTTPException(status_code=403, detail="Forbidden")
        return True

    return dependency


def require_any_permission(*permission_names: str):
    """Dependency that passes if the current user has any of the provided permissions.

    Useful for endpoints that should be accessible by either a tenant-scoped
    permission or a super-admin/global permission (for example
    'update_tenant_users' OR 'update_all_users').

    Uses pre-fetched permissions from request.state.user_permissions.
    """

    async def dependency(
        request: Request,
        current_user=Depends(get_current_user),
    ):
        if current_user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Use pre-fetched permissions from middleware
        perms = getattr(request.state, "user_permissions", [])
        for pname in permission_names:
            if pname in perms:
                # Record granted metric
                try:
                    from ..metrics import PERMISSION_CHECKS

                    if PERMISSION_CHECKS is not None:
                        PERMISSION_CHECKS.labels(permission=pname, result="granted").inc()
                except Exception:
                    pass
                return True

        # Record denied metric for all checked permissions
        try:
            from ..metrics import PERMISSION_CHECKS

            if PERMISSION_CHECKS is not None:
                for pname in permission_names:
                    PERMISSION_CHECKS.labels(permission=pname, result="denied").inc()
        except Exception:
            pass

        raise HTTPException(status_code=403, detail="Forbidden")

    return dependency


def require_role_hierarchy_for_user_management():
    """Dependency enforcing role-hierarchy: caller must have a strictly higher role
    than the target user (or the target role when creating a new user).

    The dependency is flexible: it accepts either `target_user_id` (path param)
    or `role` (intended role for a creation request). FastAPI will resolve
    these from path/query/body as appropriate.
    """

    ROLE_LEVELS = {
        "guest": 0,
        "member": 1,
        "admin": 2,
        "super_admin": 3,
    }

    async def dependency(
        target_user_id: int | None = None,
        id: int | None = None,  # Alternative parameter name for backward compatibility
        role: str | None = None,
        request: Request = None,  # type: ignore[assignment]
        current_user: TokenClaims = Depends(get_current_user),
        user_repo: UserRepository = Depends(get_user_repo),
    ):
        # Use target_user_id if provided, otherwise fall back to id
        user_id_to_check = target_user_id if target_user_id is not None else id

        # Some clients send the intended `role` as a query param; if FastAPI
        # didn't bind it to the dependency (edge cases), try to read it from
        # the Request so the check still runs reliably.
        if role is None and request is not None:
            try:
                qrole = request.query_params.get("role")
                if qrole:
                    role = qrole
                else:
                    # Try JSON body as a last resort for clients that POST JSON
                    try:
                        body = await request.json()
                        if isinstance(body, dict):
                            role = body.get("role")
                    except Exception:
                        pass
            except Exception:
                pass
        # current user id
        try:
            # current_user is now TokenClaims
            uid_str = current_user.subject
            if uid_str is None:
                raise Exception("no uid")
            uid = int(uid_str)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )

        # fetch current user record when possible
        try:
            current_obj = await user_repo.get_by_id(uid)
        except Exception:
            current_obj = None

        if current_obj is None:
            # cannot evaluate hierarchy without a current user record
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges"
            )

        current_role = getattr(current_obj, "role", "member")
        current_level = ROLE_LEVELS.get(current_role, 1)

        # If creating a user, compare against requested role
        if role is not None:
            target_level = ROLE_LEVELS.get(role, 1)
            if current_level <= target_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient role hierarchy",
                )
            return True

        # If acting on an existing user, compare roles (allow self-actions)
        if user_id_to_check is not None:
            if int(user_id_to_check) == uid:
                return True
            try:
                target_obj = await user_repo.get_by_id(int(user_id_to_check))
            except Exception:
                target_obj = None
            if target_obj is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="target user not found",
                )
            target_role = getattr(target_obj, "role", "member")
            target_level = ROLE_LEVELS.get(target_role, 1)
            if current_level <= target_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient role hierarchy",
                )
            return True

        # nothing to compare against; deny by default
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role or target_user_id required",
        )

    return dependency
