# typing import for Optional
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..deps import get_cache_client
from ..logging_config import get_logger
from ..services.auth_service import create_default_auth_service

logger = get_logger(__name__)

# imports used for tenant resolution will be loaded at runtime inside the
# dispatch method to avoid import-time DB/ORM side effects


class CurrentUserMiddleware(BaseHTTPMiddleware):
    """Resolve the current user once per request and attach to request.state.current_user.

    Behavior:
    - If Authorization header contains a Bearer token, verify it with the default
      auth service and attach the token payload to request.state.current_user.
    - Also ensure a session cache entry exists (session:{token_hash}) using the
      app.state cache client when available, otherwise fall back to deps.get_cache_client().
    - Failures to validate should not short-circuit the request; downstream
      dependencies (e.g. get_current_user) will raise auth errors when required.
    """

    async def dispatch(self, request: Request, call_next):
        # Skip health endpoints early
        path = request.url.path or ""
        if path.startswith("/health") or path.startswith("/api/v1/health"):
            return await call_next(request)

        # Resolve host-based tenant slug (left-most label) when applicable
        host = request.url.hostname or request.headers.get("host")
        slug: Optional[str] = None
        if host:
            parts = host.split(".")
            if len(parts) > 1:
                left = parts[0]
                if left not in ("localhost", "127") and not left.isdigit():
                    slug = left

        # Prepare variables used during resolution
        tenant = None
        payload = None
        auth_service = None
        claims = None
        auth_hdr = request.headers.get("authorization") or request.headers.get("Authorization")
        token = None
        if auth_hdr and auth_hdr.lower().startswith("bearer "):
            token = auth_hdr.split(" ", 1)[1].strip()

        # Try to verify token once (best-effort). We'll use the claims to
        # help resolve tenant by tenant_id if necessary and to attach
        # request.state.current_user later after checking session cache.
        if token:
            try:
                auth_service = create_default_auth_service()
                claims = auth_service.verify_token(token)
                payload = claims.to_dict()
                payload.setdefault("sub", claims.subject)
                if claims.tenant_id is not None:
                    payload.setdefault("tenant_id", claims.tenant_id)
                logger.debug(
                    "token_verified",
                    extra={"user_id": claims.subject, "tenant_id": claims.tenant_id},
                )
            except Exception as e:
                # Log verification failures for diagnostics but do not raise here
                logger.warning("token_verification_failed", extra={"error": str(e), "path": path})
                payload = None
                auth_service = None

        # Resolve tenant using DB if possible. Load DB/session-related imports at runtime
        from .. import db as db_mod

        AsyncSessionLocal = getattr(db_mod, "AsyncSessionLocal", None)

        if AsyncSessionLocal is not None:
            try:
                async with AsyncSessionLocal() as db_session:
                    from ..infrastructure.repositories import get_repositories

                    cache = getattr(request.app.state, "cache_client", None)
                    repo = get_repositories(db_session, cache=cache)["tenants"]

                    if slug:
                        tenant = await repo.get_by_slug(slug)
                        if tenant is None:
                            logger.warning(
                                "tenant_not_found_by_slug", extra={"slug": slug, "path": path}
                            )
                            return JSONResponse(
                                status_code=404, content={"detail": "Tenant not found"}
                            )
                        logger.debug(
                            "tenant_resolved_by_slug", extra={"tenant_id": tenant.id, "slug": slug}
                        )

                    # if no tenant by slug, try tenant_id from verified token claims
                    if tenant is None and payload is not None:
                        t_id = payload.get("tenant_id")
                        if t_id is not None:
                            tenant = await repo.get_by_id(int(t_id))
                            if tenant is None:
                                logger.warning(
                                    "tenant_not_found_by_id",
                                    extra={"tenant_id": t_id, "path": path},
                                )
                                return JSONResponse(
                                    status_code=404,
                                    content={"detail": "Tenant not found"},
                                )
                            logger.debug("tenant_resolved_by_token", extra={"tenant_id": tenant.id})

                    # attach tenant and enforce status
                    if tenant is not None:
                        request.state.tenant = tenant
                        if getattr(tenant, "status", "active") not in ("active", None):
                            logger.warning(
                                "tenant_not_active",
                                extra={"tenant_id": tenant.id, "status": tenant.status},
                            )
                            return JSONResponse(
                                status_code=403,
                                content={"detail": "Tenant is not active"},
                            )
            except Exception as e:
                try:
                    from ..logging_config import get_logger

                    get_logger(__name__).exception(
                        "tenant_resolution_failed", extra={"error": str(e)}
                    )
                except Exception:
                    # swallow logging failures
                    pass
                # allow exceptions to surface after logging so startup/runtime issues are visible

        # Now determine current_user: prefer TokenClaims object but ensure session exists in cache when possible
        if claims is not None and token is not None:
            # prefer request.app.state cache client, otherwise use configured get_cache_client
            cache = getattr(request.app.state, "cache_client", None)
            if cache is None:
                cache = get_cache_client()

            if cache is not None and auth_service is not None:
                access_hash = auth_service.get_token_hash(token)
                entry = await cache.get(f"session:{access_hash}")
                # Store TokenClaims object instead of dict
                request.state.current_user = claims if entry else None
            else:
                request.state.current_user = claims
        else:
            # no valid claims/token -> ensure attribute exists for downstream code
            request.state.current_user = None

        # Pre-fetch user permissions and attach to request.state for efficient access
        if request.state.current_user is not None:
            try:
                uid = int(request.state.current_user.subject)

                # CRITICAL: Verify JWT tenant_id matches resolved tenant (no DB lookup needed)
                # The tenant_id is already in the JWT claims and has been cryptographically verified
                if tenant is not None and claims is not None:
                    jwt_tenant_id = getattr(claims, "tenant_id", None)
                    if jwt_tenant_id is not None and jwt_tenant_id != tenant.id:
                        logger.error(
                            "jwt_tenant_mismatch",
                            extra={
                                "user_id": uid,
                                "jwt_tenant_id": jwt_tenant_id,
                                "resolved_tenant_id": tenant.id,
                            },
                        )
                        return JSONResponse(
                            status_code=403,
                            content={"detail": "User tenant mismatch - access denied"},
                        )

                if AsyncSessionLocal is not None:
                    async with AsyncSessionLocal() as db_session:
                        from ..infrastructure.repositories import get_repositories

                        cache = getattr(request.app.state, "cache_client", None)
                        repos = get_repositories(db_session, cache=cache)

                        # list_user_permissions now benefits from caching
                        perms = await repos["permissions"].list_user_permissions(uid)
                        request.state.user_permissions = perms
                        logger.debug(
                            "user_permissions_loaded",
                            extra={"user_id": uid, "permission_count": len(perms)},
                        )
                else:
                    request.state.user_permissions = []
            except Exception as e:
                # Best-effort: if permissions fetch fails, set empty list and log
                try:
                    from ..logging_config import get_logger

                    get_logger(__name__).debug(
                        "user_permissions_fetch_failed",
                        extra={"error": str(e)},
                    )
                except Exception:
                    pass
                request.state.user_permissions = []
        else:
            request.state.user_permissions = []

        return await call_next(request)
