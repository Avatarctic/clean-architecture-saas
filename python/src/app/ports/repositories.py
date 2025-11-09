"""Public API for repository and service protocols.

This module provides a single import point for all repository protocols.
Internal implementation is organized in subdirectories.
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
    "UserRepository",
    "TenantRepository",
    "EmailTokenRepository",
    "RolePermissionRepository",
    "EmailSender",
    "FeatureFlagRepository",
]
