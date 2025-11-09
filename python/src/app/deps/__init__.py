"""Dependency injection for FastAPI.

This package provides all FastAPI dependency functions organized by responsibility:
- providers: Singleton providers (settings, auth service, cache, email)
- injection: Repository and service dependency injection
- auth: Authorization decorators and rate limiting
"""

from . import providers as _providers
from .auth import (
    require_any_permission,
    require_permission,
    require_rate_limit,
    require_role_hierarchy_for_user_management,
)
from .injection import (
    get_audit_repo,
    get_current_tenant_id,
    get_current_user,
    get_db,
    get_email_tokens_repo,
    get_feature_flag_repo,
    get_permission_repo,
    get_session_service,
    get_tenant_repo,
    get_tenant_service,
    get_tokens_repo,
    get_user_repo,
    get_user_service,
    oauth2_scheme,
)
from .providers import (
    get_auth_service,
    get_cache_client,
    get_cache_from_request,
    get_email_sender,
    get_settings,
)


def __getattr__(name: str):
    """Forward dynamic attributes from providers module."""
    if name in ("_app_cache_client", "_app_email_sender"):
        return getattr(_providers, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    # Providers
    "get_settings",
    "get_auth_service",
    "get_email_sender",
    "get_cache_client",
    "get_cache_from_request",
    # Injection
    "get_db",
    "get_user_repo",
    "get_tenant_repo",
    "get_tokens_repo",
    "get_email_tokens_repo",
    "get_permission_repo",
    "get_feature_flag_repo",
    "get_audit_repo",
    "get_user_service",
    "get_tenant_service",
    "get_session_service",
    "get_current_user",
    "get_current_tenant_id",
    "oauth2_scheme",
    # Auth
    "require_permission",
    "require_any_permission",
    "require_role_hierarchy_for_user_management",
    "require_rate_limit",
]
