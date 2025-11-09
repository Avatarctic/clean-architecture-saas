"""Ports package - defines interfaces for external dependencies.

Exports repository protocols and service interfaces for dependency inversion.
"""

from .email import EmailSender
from .repositories import (
    EmailTokenRepository,
    FeatureFlagRepository,
    RolePermissionRepository,
    TenantRepository,
    UserRepository,
)

__all__ = [
    # Repository protocols
    "UserRepository",
    "TenantRepository",
    "EmailTokenRepository",
    "RolePermissionRepository",
    "FeatureFlagRepository",
    "EmailSender",
]
