from typing import List

from fastapi import APIRouter, Depends

from ..deps import get_db, require_permission, require_rate_limit
from ..schemas.audit import AuditEventResponse

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get(
    "/logs",
    response_model=List[AuditEventResponse],
    dependencies=[
        Depends(require_permission("view_audit_log")),
        Depends(require_rate_limit),
    ],
)
async def list_events(limit: int = 100, db_session=Depends(get_db)):
    # direct DB access for simplicity
    from sqlalchemy import select

    from ..infrastructure.db.models import AuditModel

    # order by timestamp (new column) descending
    res = await db_session.execute(
        select(AuditModel).order_by(AuditModel.timestamp.desc()).limit(limit)
    )
    rows = res.scalars().all()
    return [
        AuditEventResponse(
            id=r.id,  # type: ignore[arg-type]
            user_id=r.user_id,  # type: ignore[arg-type]
            tenant_id=r.tenant_id,  # type: ignore[arg-type]
            action=r.action,  # type: ignore[arg-type]
            resource=r.resource,  # type: ignore[arg-type]
            resource_id=r.resource_id,  # type: ignore[arg-type]
            details=r.details,  # type: ignore[arg-type]
            ip_address=r.ip_address,  # type: ignore[arg-type]
            user_agent=r.user_agent,  # type: ignore[arg-type]
            timestamp=str(r.timestamp),
        )
        for r in rows
    ]
