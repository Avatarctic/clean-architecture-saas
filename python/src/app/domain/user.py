import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    id: Optional[int]
    tenant_id: int
    email: str
    hashed_password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = "member"
    email_verified: bool = False
    audit_enabled: bool = False
    is_active: bool = True
    last_login_at: Optional[datetime.datetime] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.datetime.now(datetime.timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.datetime.now(datetime.timezone.utc)
