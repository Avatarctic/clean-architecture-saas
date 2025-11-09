"""Repository adapters package: explicit public exports.

Call `get_repositories(db_session, cache=None)` to obtain repository instances.
"""


def get_repositories(db_session, cache=None):
    """Return a simple container of repository instances wired to the given db_session and optional cache."""
    # Memoize repositories per (db_session, cache) so callers get stable
    # instances for the same db_session/cache pair instead of recreating
    # objects on each call. This helps identity checks in callers and
    # avoids repeatedly constructing wrapper objects.
    from weakref import WeakKeyDictionary

    # Use a module-level weak map keyed by db_session. Each entry
    # maps a cache-key (cache id or None) to the repository dict.
    if "_repos_map" not in globals():
        globals()["_repos_map"] = WeakKeyDictionary()

    repos_map = globals()["_repos_map"]

    # Determine a cache key for the provided cache object. Use id(cache)
    # to distinguish different cache clients; None is allowed.
    cache_key = None if cache is None else (id(cache), type(cache))

    # Check if we already have repositories for this (db_session, cache) pair
    entry = repos_map.get(db_session)
    if entry is None:
        entry = {}
        repos_map[db_session] = entry
    else:
        existing = entry.get(cache_key)
        if existing is not None:
            return existing
    # import concrete implementations lazily so callers obtain repositories
    # only via the factory API (get_repositories) rather than top-level imports
    from .audit_repository import SqlAlchemyAuditRepository
    from .feature_repository import SqlAlchemyFeatureFlagRepository
    from .permissions_repository import SqlAlchemyPermissionRepository
    from .tenants_repository import SqlAlchemyTenantRepository
    from .tokens_repository import SqlAlchemyTokensRepository
    from .users_repository import SqlAlchemyUserRepository

    users = SqlAlchemyUserRepository(db_session)
    tenants = SqlAlchemyTenantRepository(db_session)
    features = SqlAlchemyFeatureFlagRepository(db_session)
    tokens = SqlAlchemyTokensRepository(db_session)
    audit = SqlAlchemyAuditRepository(db_session)
    permissions = SqlAlchemyPermissionRepository(db_session)

    # Email tokens require cache - create only if cache is available
    email_tokens = None

    # Apply caching wrappers when cache present
    if cache is not None:
        from .caching import (
            CachingFeatureFlagRepository,
            CachingPermissionRepository,
            CachingTenantRepository,
            CachingTokensRepository,
            CachingUserRepository,
        )
        from .email_token_cache_repository import EmailTokenCacheRepository
        from .session_cache_repository import SessionCacheRepository

        users = CachingUserRepository(users, cache)  # type: ignore[assignment]
        tenants = CachingTenantRepository(tenants, cache)  # type: ignore[assignment]
        features = CachingFeatureFlagRepository(features, cache)  # type: ignore[assignment]
        permissions = CachingPermissionRepository(permissions, cache)  # type: ignore[assignment]
        tokens = CachingTokensRepository(tokens, SessionCacheRepository(cache))  # type: ignore[assignment]
        email_tokens = EmailTokenCacheRepository(cache)

    result = {
        "users": users,
        "tenants": tenants,
        "feature_flags": features,
        "permissions": permissions,
        "tokens": tokens,
        "audit": audit,
        "email_tokens": email_tokens,
    }

    # Store into cache so subsequent calls with same db_session+cache return same object
    entry[cache_key] = result

    return result


__all__ = ["get_repositories"]
