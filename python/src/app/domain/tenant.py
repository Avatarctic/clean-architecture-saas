import datetime
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Tenant:
    id: Optional[int]
    name: str
    slug: Optional[str] = None
    domain: Optional[str] = None
    plan: str = "free"
    status: str = "active"
    settings: Any = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.datetime.now(datetime.timezone.utc)
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.settings is None:
            self.settings = {}

    def can_transition_to(self, target: str) -> bool:
        """Return whether tenant may transition from current status to target.

        Rules (conservative):
        - active -> suspended, canceled
        - suspended -> active, canceled
        - canceled -> no transitions
        """
        src = (self.status or "").lower()
        tgt = (target or "").lower()
        if src == "canceled":
            return False
        if src == "active" and tgt in ("suspended", "canceled", "active"):
            return True
        if src == "suspended" and tgt in ("active", "canceled", "suspended"):
            return True
        # default: conservative deny
        return False
