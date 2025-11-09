"""Authentication domain models and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(slots=True)
class AuthTokens:
    """Bundle of issued tokens returned to clients."""

    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None


@dataclass(slots=True)
class TokenClaims:
    """Structured representation of JWT claims."""

    subject: str
    tenant_id: Optional[int] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def _coerce_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            try:
                return datetime.fromisoformat(str(value))
            except Exception:
                return None

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"sub": self.subject}
        if self.tenant_id is not None:
            payload["tenant_id"] = self.tenant_id
        payload.update(self.extra)
        return payload

    def to_dict(self) -> Dict[str, Any]:
        data = self.to_payload()
        if self.issued_at is not None:
            data["iat"] = int(self.issued_at.timestamp())
        if self.expires_at is not None:
            data["exp"] = int(self.expires_at.timestamp())
        return data

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "TokenClaims":
        data = dict(payload)
        subject = str(data.pop("sub"))
        tenant_id = cls._coerce_int(data.pop("tenant_id", None))
        iat_raw = data.pop("iat", None)
        exp_raw = data.pop("exp", None)
        issued_at = cls._coerce_datetime(iat_raw)
        expires_at = cls._coerce_datetime(exp_raw)
        return cls(
            subject=subject,
            tenant_id=tenant_id,
            issued_at=issued_at,
            expires_at=expires_at,
            extra=data,
        )


__all__ = ["AuthTokens", "TokenClaims"]
