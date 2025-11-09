from typing import Any, Optional

from pydantic import BaseModel, EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None


class TokenRequest(BaseModel):
    email: EmailStr
    password: str


class UserCreateRequest(BaseModel):
    tenant_id: Optional[int] = None
    tenant_name: Optional[str] = None
    email: EmailStr
    password: str
    # optional tenant creation overrides when registering a new tenant alongside a user
    tenant_slug: Optional[str] = None
    tenant_domain: Optional[str] = None
    tenant_plan: Optional[str] = None
    tenant_status: Optional[str] = None
    tenant_settings: Optional[dict] = None


class UserResponse(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_active: bool
    email_verified: bool
    audit_enabled: bool
    last_login_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def user_to_response(u: Any) -> UserResponse:
    """Convert a user domain/repo object to a UserResponse safely.

    Accepts any object/dict-like with attributes used by UserResponse.
    """
    return UserResponse(
        id=int(u.id),
        tenant_id=int(u.tenant_id),
        email=u.email,
        first_name=getattr(u, "first_name", None),
        last_name=getattr(u, "last_name", None),
        role=u.role,
        is_active=getattr(u, "is_active", True),
        email_verified=getattr(u, "email_verified", False),
        audit_enabled=getattr(u, "audit_enabled", False),
        last_login_at=(
            str(u.last_login_at) if getattr(u, "last_login_at", None) is not None else None
        ),
        created_at=(str(u.created_at) if getattr(u, "created_at", None) is not None else None),
        updated_at=(str(u.updated_at) if getattr(u, "updated_at", None) is not None else None),
    )
