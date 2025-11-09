"""Schema exports for API request/response models."""

from .audit import AuditEventResponse, AuditLogListResponse
from .auth import (
    RefreshRequest,
    RefreshResponse,
    TokenRequest,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
    user_to_response,
)
from .feature_flag import (
    FeatureFlagActionResponse,
    FeatureFlagCreateRequest,
    FeatureFlagEvaluateRequest,
    FeatureFlagEvaluationResponse,
    FeatureFlagListResponse,
    FeatureFlagResponse,
    FeatureFlagUpdateRequest,
)
from .permission import (
    AssignPermissionRequest,
    AvailablePermissionsResponse,
    PermissionActionResponse,
    PermissionResponse,
    RemovePermissionRequest,
    RolePermissionsResponse,
    RoleResponse,
    SetRolePermissionsRequest,
)
from .tenant import TenantCreateRequest, TenantResponse
from .user import (
    ChangePasswordRequest,
    RevokeAllSessionsResponse,
    RevokeSessionResponse,
    SessionListResponse,
    SessionResponse,
    UpdateEmailRequest,
    UserActionResponse,
    UserUpdateRequest,
)

__all__ = [
    # Auth schemas
    "TokenRequest",
    "TokenResponse",
    "UserCreateRequest",
    "UserResponse",
    "RefreshRequest",
    "RefreshResponse",
    "user_to_response",
    # Tenant schemas
    "TenantCreateRequest",
    "TenantResponse",
    # User management schemas
    "UserUpdateRequest",
    "ChangePasswordRequest",
    "UpdateEmailRequest",
    "SessionResponse",
    "SessionListResponse",
    "RevokeSessionResponse",
    "RevokeAllSessionsResponse",
    "UserActionResponse",
    # Permission schemas
    "PermissionResponse",
    "RoleResponse",
    "RolePermissionsResponse",
    "AvailablePermissionsResponse",
    "SetRolePermissionsRequest",
    "AssignPermissionRequest",
    "RemovePermissionRequest",
    "PermissionActionResponse",
    # Feature flag schemas
    "FeatureFlagCreateRequest",
    "FeatureFlagUpdateRequest",
    "FeatureFlagEvaluateRequest",
    "FeatureFlagResponse",
    "FeatureFlagEvaluationResponse",
    "FeatureFlagListResponse",
    "FeatureFlagActionResponse",
    # Audit schemas
    "AuditEventResponse",
    "AuditLogListResponse",
]
