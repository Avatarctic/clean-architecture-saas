from typing import Optional

from pydantic import BaseModel


class TenantCreateRequest(BaseModel):
    name: str
    slug: Optional[str] = None
    domain: Optional[str] = None
    plan: Optional[str] = None
    status: Optional[str] = None
    settings: Optional[dict] = None


class TenantResponse(BaseModel):
    id: int
    name: str
    slug: Optional[str] = None
    domain: Optional[str] = None
    plan: Optional[str] = None
    status: Optional[str] = None
    settings: Optional[dict] = None
    created_at: Optional[str]
    updated_at: Optional[str]
