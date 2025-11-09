from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.audit import AuditEvent
from ..db import models


class SqlAlchemyAuditRepository:
    def __init__(self, db_session: AsyncSession):
        """Initialize audit repository with a database session.

        Args:
            db_session: SQLAlchemy async session instance
        """
        self.db_session = db_session

    async def log_event(
        self,
        current_user: Optional[object],
        current_tenant: Optional[object],
        event: AuditEvent,
    ) -> None:
        # derive user_id and tenant_id from provided context
        user_id = None
        tenant_id = None
        try:
            # current_user may be TokenClaims, dict, or object with 'id'
            from ...domain.auth import TokenClaims

            if isinstance(current_user, TokenClaims):
                user_id = int(current_user.subject) if current_user.subject else None
            elif isinstance(current_user, dict):
                sub_or_id = current_user.get("sub") or current_user.get("id")
                user_id = int(sub_or_id) if sub_or_id is not None else None
            else:
                # allow object-like current_user
                uid = getattr(current_user, "id", None)
                user_id = int(uid) if uid is not None else None
        except Exception as e:
            try:
                from ..logging_config import get_logger

                get_logger(__name__).debug("audit_userid_parse_failed", extra={"error": str(e)})
            except Exception:
                pass
            user_id = None
        try:
            # current_tenant may be an object with id attribute or a dict
            if isinstance(current_tenant, dict):
                tenant_id_val = current_tenant.get("id")
                tenant_id = int(tenant_id_val) if tenant_id_val is not None else None
            else:
                tid = getattr(current_tenant, "id", None)
                tenant_id = int(tid) if tid is not None else None
        except Exception as e:
            try:
                from ..logging_config import get_logger

                get_logger(__name__).debug("audit_tenantid_parse_failed", extra={"error": str(e)})
            except Exception:
                pass
            tenant_id = None

        # Check audit preference from current_user
        try:
            audit_pref = None
            from ...domain.auth import TokenClaims

            if isinstance(current_user, TokenClaims):
                # TokenClaims may have audit_enabled in extra dict
                audit_pref = current_user.extra.get("audit_enabled")
            elif isinstance(current_user, dict):
                # current_user may include an 'audit_enabled' flag
                audit_pref = current_user.get("audit_enabled")
            else:
                audit_pref = getattr(current_user, "audit_enabled", None)
            # if audit_pref explicitly False, skip
            if audit_pref is False:
                return
            # otherwise, if not provided, fall back to DB lookup when user_id present
            if audit_pref is None and user_id is not None:
                q = await self.db_session.execute(
                    select(models.UserModel.audit_enabled).where(models.UserModel.id == user_id)
                )
                r = q.scalars().first()
                if r is False:
                    return
        except Exception as e:
            try:
                from ..logging_config import get_logger

                get_logger(__name__).debug("audit_pref_check_failed", extra={"error": str(e)})
            except Exception:
                pass
            # if the check fails, fall back to best-effort auditing
            pass

        record = event.to_record()
        action_value = record.get("action", "")
        details_payload = record.get("details", {}) or {}
        ip_address = record.get("ip_address")
        user_agent = record.get("user_agent")
        timestamp_value = record.get("timestamp") or datetime.utcnow()

        # Extract resource and resource_id from event (they may be in details)
        resource_value = event.resource_value()
        resource_id_value = event.resource_id

        audit = models.AuditModel(
            user_id=user_id,
            tenant_id=tenant_id,
            action=action_value,
            resource=resource_value,
            resource_id=resource_id_value,
            details=details_payload,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=timestamp_value,
        )
        self.db_session.add(audit)
        try:
            await self.db_session.flush()
        except Exception as e:
            try:
                from ..logging_config import get_logger

                get_logger(__name__).debug("audit_flush_failed", extra={"error": str(e)})
            except Exception:
                pass
            # best-effort: swallow flush errors so callers don't fail due to audit issues
            pass
