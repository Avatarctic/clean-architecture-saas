"""Audit domain models and value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Dict, Optional, Union


class AuditAction(StrEnum):
    """Canonical audit actions across the platform."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    TOKEN_ISSUED = "token_issued"
    TOKEN_REVOKED = "token_revoked"
    REGISTER = "register"


class AuditResource(StrEnum):
    """Resource identifiers captured by audit events."""

    USER = "user"
    TENANT = "tenant"
    PERMISSION = "permission"
    FEATURE_FLAG = "feature_flag"
    SESSION = "session"
    AUTH = "auth"
    TOKEN = "token"


AuditActionLike = Union[AuditAction, str]
AuditResourceLike = Union[AuditResource, str, None]


@dataclass(slots=True)
class AuditEvent:
    """Immutable representation of an audit event prior to persistence."""

    action: AuditActionLike
    resource: AuditResourceLike = None
    resource_id: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def action_value(self) -> str:
        """Return the action as a plain string for persistence."""

        return str(self.action)

    def resource_value(self) -> Optional[str]:
        """Return the resource identifier as a string when available."""

        if self.resource is None:
            return None
        return str(self.resource)

    def to_record(self) -> Dict[str, Any]:
        """Materialize the event into a serializable dictionary."""

        base_details: Dict[str, Any] = dict(self.details or {})
        record: Dict[str, Any] = {
            "action": self.action_value(),
            "details": base_details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "timestamp": self.timestamp,
        }
        resource = self.resource_value()
        if resource is not None:
            record["details"].setdefault("resource", resource)
        if self.resource_id is not None:
            record["details"].setdefault("resource_id", self.resource_id)
        if self.metadata:
            record["details"].setdefault("meta", self.metadata)
        return record


async def log_audit_event(
    audit_repo,
    user: Any,
    action: AuditAction,
    resource: AuditResource,
    details: dict,
    resource_id: Optional[int] = None,
    request: Optional[Any] = None,
):
    """Helper to log audit events with consistent formatting.

    Args:
        audit_repo: Audit repository instance (can be None, will skip logging)
        user: User object with id, email, tenant_id, and audit_enabled attributes
        action: AuditAction enum value
        resource: AuditResource enum value
        details: Dictionary with event details
        resource_id: Optional resource ID (defaults to user.id)
        request: Optional FastAPI Request for IP/user-agent extraction
    """
    if audit_repo is None:
        return

    try:
        # Import logger here to avoid circular dependency
        from ..logging_config import get_logger

        logger = get_logger(__name__)

        # Extract user info
        user_id = int(user.id)
        current_user = {
            "id": user_id,
            "email": getattr(user, "email", None),
            "audit_enabled": getattr(user, "audit_enabled", True),
        }
        current_tenant = {"id": user.tenant_id}

        # Extract request metadata
        ip_address = None
        user_agent = None
        if request is not None:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

        # Create and log event
        event = AuditEvent(
            action=action,
            resource=resource,
            resource_id=resource_id if resource_id is not None else user_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await audit_repo.log_event(current_user, current_tenant, event)

        # Record audit event metric
        try:
            from ..metrics import AUDIT_EVENTS

            if AUDIT_EVENTS is not None:
                AUDIT_EVENTS.labels(action=str(action), resource=str(resource)).inc()
        except Exception:
            pass  # Don't fail audit on metrics errors
    except Exception as e:
        try:
            from ..logging_config import get_logger

            logger = get_logger(__name__)
            logger.debug("audit_log_failed", extra={"action": action, "error": str(e)})
        except Exception:
            pass


__all__ = [
    "AuditAction",
    "AuditResource",
    "AuditEvent",
    "AuditActionLike",
    "AuditResourceLike",
    "log_audit_event",
]
