"""Repository protocols for data access layer abstraction."""

from .feature_flag import FeatureFlagRepository
from .permission import RolePermissionRepository
from .tenant import TenantRepository
from .token import EmailTokenRepository
from .user import UserRepository

__all__ = [
    "UserRepository",
    "TenantRepository",
    "EmailTokenRepository",
    "RolePermissionRepository",
    "FeatureFlagRepository",
]
