"""Caching repository decorators.

This package contains cache-aside wrappers for all repositories that support caching.
Each caching repository wraps a base repository and adds transparent caching with
Redis or in-memory cache.
"""

from .feature_flag_caching import CachingFeatureFlagRepository
from .permission_caching import CachingPermissionRepository
from .tenant_caching import CachingTenantRepository
from .tokens_caching import CachingTokensRepository
from .user_caching import CachingUserRepository

__all__ = [
    "CachingTenantRepository",
    "CachingUserRepository",
    "CachingPermissionRepository",
    "CachingFeatureFlagRepository",
    "CachingTokensRepository",
]
