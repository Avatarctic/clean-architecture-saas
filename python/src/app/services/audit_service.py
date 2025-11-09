from typing import Optional

from ..domain.audit import AuditActionLike, AuditEvent, AuditResource, AuditResourceLike
from ..ports.audit import AuditRepository


class AuditService:
    def __init__(self, repo: AuditRepository):
        self.repo = repo

    async def log(
        self,
        current_user: Optional[object],
        current_tenant: Optional[object],
        action: AuditActionLike,
        resource: AuditResourceLike = AuditResource.AUTH,
        detail: Optional[dict | str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        if isinstance(detail, dict):
            details_dict = detail
        elif detail is None:
            details_dict = None
        else:
            details_dict = {"message": detail}
        event = AuditEvent(
            action=action,
            resource=resource,
            details=details_dict,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.repo.log_event(current_user, current_tenant, event)
