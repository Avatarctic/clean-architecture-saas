"""Shared utilities for caching repositories."""

import json
from datetime import datetime
from typing import Any, Optional

from src.app.domain.tenant import Tenant as DomainTenant


def serialize(obj: Any) -> str:
    """Serialize an object to JSON string."""
    try:
        return json.dumps(obj, default=lambda o: o.__dict__)
    except TypeError:
        return str(obj)


def deserialize_tenant(s: Any) -> Optional[DomainTenant]:
    """Deserialize a cached tenant value back to DomainTenant object."""
    if s is None:
        return None
    if isinstance(s, DomainTenant):
        return s
    # cache stores JSON serializable dicts via set/get helpers; accept dict
    if isinstance(s, dict):
        # convert ISO timestamps back to datetimes when present
        if s.get("created_at"):
            s["created_at"] = datetime.fromisoformat(s["created_at"])
        if s.get("updated_at"):
            s["updated_at"] = datetime.fromisoformat(s["updated_at"])
        return DomainTenant(**s)
    if isinstance(s, str):
        try:
            d = json.loads(s)
        except json.JSONDecodeError:
            return None
        if d.get("created_at"):
            d["created_at"] = datetime.fromisoformat(d["created_at"])
        if d.get("updated_at"):
            d["updated_at"] = datetime.fromisoformat(d["updated_at"])
        return DomainTenant(**d)
    return None
