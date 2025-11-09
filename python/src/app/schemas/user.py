from typing import List, Optional

from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    """Request model for creating a new user."""

    email: str
    password: str
    role: Optional[str] = "member"


class UserUpdateRequest(BaseModel):
    """Request model for updating user fields."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    email_verified: Optional[bool] = None
    audit_enabled: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    """Request model for changing user password."""

    new_password: str


class UpdateEmailRequest(BaseModel):
    """Request model for updating user email."""

    new_email: str


class SessionResponse(BaseModel):
    """Response model for user session information."""

    token_hash: str
    user_id: int
    created_at: str
    expires_at: str
    last_used_at: Optional[str] = None


class SessionListResponse(BaseModel):
    """Response model for list of user sessions."""

    sessions: List[SessionResponse]


class RevokeSessionResponse(BaseModel):
    """Response model for session revocation."""

    revoked: bool


class RevokeAllSessionsResponse(BaseModel):
    """Response model for revoking all user sessions."""

    revoked: bool
    revoked_count: Optional[int] = None


class UserActionResponse(BaseModel):
    """Generic response for user actions (update, delete, password change)."""

    updated: Optional[bool] = None
    deleted: Optional[bool] = None
    changed: Optional[bool] = None
