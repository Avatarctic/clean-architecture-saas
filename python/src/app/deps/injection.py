"""Dependency injection functions for FastAPI.

This module provides FastAPI Depends() functions for repositories, services,
database sessions, and authentication.
"""

import sys
from typing import Any, AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..ports.repositories import TenantRepository, UserRepository
from .providers import get_auth_service, get_cache_client

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session.

    Import the db module at call time so any runtime rebinds performed by
    `setup_db.create_all()` are respected (for example when falling back to sqlite).
    """
    import importlib

    db_mod = importlib.import_module(".db", package="src.app")
    AsyncSessionLocal = db_mod.AsyncSessionLocal
    async with AsyncSessionLocal() as db_session:
        yield db_session


async def get_user_repo(db_session: AsyncSession = Depends(get_db)) -> UserRepository:
    """Get user repository with caching if cache is available."""
    cache = getattr(sys.modules.get("src.app.deps.providers"), "_app_cache_client", None)
    from ..infrastructure.repositories import get_repositories

    repos = get_repositories(db_session, cache=cache)
    result: UserRepository = repos.get("users")  # type: ignore[assignment]
    return result


async def get_tenant_repo(db_session: AsyncSession = Depends(get_db)) -> TenantRepository:
    """Get tenant repository with caching if cache is available."""
    cache = getattr(sys.modules.get("src.app.deps.providers"), "_app_cache_client", None)
    from ..infrastructure.repositories import get_repositories

    repos = get_repositories(db_session, cache=cache)
    result: TenantRepository = repos["tenants"]  # type: ignore[assignment]
    return result


async def get_tokens_repo(db_session: AsyncSession = Depends(get_db)):
    """Get tokens repository instance from the repository factory."""
    cache = getattr(sys.modules.get("src.app.deps.providers"), "_app_cache_client", None)
    from ..infrastructure.repositories import get_repositories

    repos = get_repositories(db_session, cache=cache)
    return repos.get("tokens")


async def get_email_tokens_repo(db_session: AsyncSession = Depends(get_db)):
    """Get email tokens repository instance from the repository factory.

    Email tokens are cache-only and require Redis/cache to be available.
    Returns None if cache is not configured.
    """
    cache = getattr(sys.modules.get("src.app.deps.providers"), "_app_cache_client", None)
    from ..infrastructure.repositories import get_repositories

    repos = get_repositories(db_session, cache=cache)
    return repos.get("email_tokens")


async def get_permission_repo(db_session: AsyncSession = Depends(get_db)):
    """Get permission repository with caching if cache is available.

    Returns the caching-wrapped permission repo when an app cache is configured,
    otherwise returns the raw SqlAlchemyPermissionRepository instance. As a
    compatibility fallback, if a dedicated permission repo is not wired, the
    tenant repo is returned (it provides delegated permission methods).
    """
    cache = getattr(sys.modules.get("src.app.deps.providers"), "_app_cache_client", None)
    from ..infrastructure.repositories import get_repositories

    repos = get_repositories(db_session, cache=cache)
    perms = repos.get("permissions")
    if perms is not None:
        return perms
    # fallback: return tenant repo (may expose permission methods via delegation)
    return repos.get("tenants")


async def get_feature_flag_repo(db_session: AsyncSession = Depends(get_db)):
    """Get feature flag repository with caching if cache is available."""
    cache = getattr(sys.modules.get("src.app.deps.providers"), "_app_cache_client", None)
    from ..infrastructure.repositories import get_repositories

    repos = get_repositories(db_session, cache=cache)
    return repos.get("feature_flags")


async def get_audit_repo(db_session: AsyncSession = Depends(get_db)):
    """Get audit repository instance from the repository factory.

    Returns the audit repository (currently not cached).
    """
    cache = getattr(sys.modules.get("src.app.deps.providers"), "_app_cache_client", None)
    from ..infrastructure.repositories import get_repositories

    repos = get_repositories(db_session, cache=cache)
    return repos.get("audit")


async def get_user_service(
    user_repo: UserRepository = Depends(get_user_repo),
    email_tokens_repo=Depends(get_email_tokens_repo),
) -> Any:
    """Get UserService instance."""
    from ..services.user_service import UserService

    return UserService(user_repo, email_tokens_repo)


async def get_tenant_service(
    tenant_repo: TenantRepository = Depends(get_tenant_repo),
) -> Any:
    """Get TenantService instance."""
    from ..services.tenant_service import TenantService

    return TenantService(tenant_repo)


async def get_session_service(
    tokens_repo=Depends(get_tokens_repo),
) -> Any:
    """Get SessionService instance."""
    cache = getattr(sys.modules.get("src.app.deps.providers"), "_app_cache_client", None)
    from ..services.session_service import SessionService

    return SessionService(tokens_repo, cache)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    tenant_repo: object = Depends(get_tenant_repo),
    tokens_repo=Depends(get_tokens_repo),
    request: Request = None,  # type: ignore[assignment]
):
    """Return TokenClaims object for the authenticated user.

    If middleware already resolved current_user, returns that.
    Otherwise verifies the token and returns TokenClaims.
    """
    # If a middleware already resolved and attached current_user to request.state,
    # prefer that to avoid re-validating the token and extra cache/DB lookups.
    if request is not None and getattr(request.state, "current_user", None) is not None:
        # Middleware now stores TokenClaims; return it directly
        return request.state.current_user

    try:
        auth = get_auth_service()
        claims = auth.verify_token(token)
        # check blacklist via repository if available
        try:
            if tokens_repo is not None:
                is_blacklisted = await tokens_repo.is_token_blacklisted(token)
                if is_blacklisted:
                    raise Exception("token is blacklisted")
        except AttributeError as e:
            # tokens repo may not implement blacklist checks; continue
            logger = __import__("structlog").get_logger(__name__)
            logger.debug("tokens_repo_missing_blacklist", extra={"error": str(e)})
        # also ensure session exists in cache (session:{access_token_hash})
        try:
            access_hash = auth.get_token_hash(token)
            cache = get_cache_client()
            entry = await cache.get(f"session:{access_hash}")
            if not entry:
                # Cache miss - check if token is blacklisted before rejecting
                # This prevents valid tokens from being rejected after cache eviction
                if tokens_repo is not None:
                    try:
                        is_blacklisted = await tokens_repo.is_token_blacklisted(token)
                        if is_blacklisted:
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Token has been revoked",
                            )
                        # Token is valid but not in cache - re-add it
                        from ..config import Settings

                        ttl = Settings().access_token_ttl_seconds
                        await cache.set(f"session:{access_hash}", token, ex=ttl)
                        return claims
                    except HTTPException:
                        raise
                    except Exception as e:
                        # If blacklist check fails, log and reject to be safe
                        try:
                            import structlog

                            structlog.get_logger(__name__).warning(
                                "blacklist_check_failed_cache_miss", extra={"error": str(e)}
                            )
                        except Exception:
                            pass
                # If no tokens_repo or check failed, reject the token
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found"
                )
        except HTTPException:
            # propagate explicit 401 raised above
            raise
        except Exception as e:
            # Any unexpected cache errors should be logged and treated as
            # an authentication failure to avoid leaking internal state.
            try:
                import structlog

                structlog.get_logger(__name__).exception("cache_read_error", error=str(e))
            except Exception:
                # swallow logging failures to avoid breaking auth flow
                pass
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return claims
    except Exception as e:
        try:
            import structlog

            structlog.get_logger(__name__).exception("token_verification_failed", error=str(e))
        except Exception:
            # swallow logging failures
            pass
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_tenant_id(request: Request) -> int:
    """Extract tenant_id from pre-resolved tenant in request.state.

    The CurrentUserMiddleware already resolves tenant once per request via:
    - Host-based slug resolution (acme.example.com -> 'acme')
    - JWT tenant_id claim fallback
    - Cross-verification (slug vs JWT)

    Returns the tenant's ID or raises 404 if tenant not found.
    """
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    tenant_id = getattr(tenant, "id", None)
    if tenant_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant ID not available")
    return int(tenant_id)
