from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    """Response model for an audit event."""

    id: int
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None
    action: str
    resource: str
    resource_id: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: str


class AuditLogListResponse(BaseModel):
    """Response model for listing audit events."""

    events: List[AuditEventResponse]
    total: Optional[int] = None
