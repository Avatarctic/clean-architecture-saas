from typing import Optional, Protocol

from ..domain.audit import AuditEvent


class AuditRepository(Protocol):
    async def log_event(
        self,
        current_user: Optional[object],
        current_tenant: Optional[object],
        event: AuditEvent,
    ) -> None: ...
