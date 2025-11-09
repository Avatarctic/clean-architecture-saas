from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class FeatureFlagRollout:
    percentage: int = 0
    strategy: str = "random"


@dataclass
class FeatureFlagCondition:
    attribute: str
    operator: str
    value: Any

    def evaluate(self, context: "FeatureFlagContext") -> bool:
        # simple operators: equals, in, contains
        val = context.custom.get(self.attribute)
        if self.operator == "equals":
            return bool(val == self.value)
        if self.operator == "in":
            try:
                return bool(val in list(self.value))
            except Exception as e:
                logger.debug(
                    "feature_condition_in_eval_failed",
                    extra={
                        "attribute": self.attribute,
                        "operator": self.operator,
                        "error": str(e),
                    },
                )
                return False
        if self.operator == "contains":
            try:
                return isinstance(val, str) and (self.value in val)
            except Exception as e:
                logger.debug(
                    "feature_condition_contains_eval_failed",
                    extra={
                        "attribute": self.attribute,
                        "operator": self.operator,
                        "error": str(e),
                    },
                )
                return False
        return False


@dataclass
class FeatureFlagRule:
    id: Optional[str]
    conditions: List[FeatureFlagCondition]
    value: Any
    rollout: int = 100

    def evaluate(self, context: "FeatureFlagContext") -> bool:
        # all conditions must match
        for c in self.conditions:
            if not c.evaluate(context):
                return False
        # check rollout
        return is_in_rollout(context.user_id, self.rollout)


@dataclass
class FeatureFlagContext:
    user_id: Optional[int | str | uuid.UUID]
    tenant_id: Optional[int | str | uuid.UUID]
    role: Optional[str]
    plan: Optional[str]
    custom: Dict[str, Any]


def is_in_rollout(user_id: Optional[int | str | uuid.UUID], percentage: int) -> bool:
    if percentage >= 100:
        return True
    if percentage <= 0:
        return False
    if user_id is None:
        return False
    # Normalize: if it's a UUID string, parse; if int-like, use int; otherwise hash
    try:
        if isinstance(user_id, uuid.UUID):
            uid = user_id
        else:
            uid = uuid.UUID(str(user_id))
        b = uid.bytes[:4]
        h = (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]
        return (h % 100) < percentage
    except Exception:
        # fallback: try int
        try:
            i = int(user_id)
            return (i % 100) < percentage
        except Exception:
            # final fallback: use builtin hash
            return (abs(hash(str(user_id))) % 100) < percentage


class FeatureFlag:
    def __init__(
        self,
        *,
        id: Optional[Any] = None,
        name: str = "",
        key: str = "",
        description: Optional[str] = None,
        type: str = "boolean",
        is_enabled: bool = False,
        enabled_value: Any = None,
        default_value: Any = None,
        rules: Optional[List[Dict[str, Any]]] = None,
        rollout: Optional[Dict[str, Any]] = None,
    ):
        self.id = id
        self.name = name
        self.key = key
        self.description = description
        self.type = type
        self.is_enabled = bool(is_enabled)
        self.enabled_value = enabled_value
        self.default_value = default_value
        self.rules = []
        if rules:
            for r in rules:
                conds = [FeatureFlagCondition(**c) for c in (r.get("conditions") or [])]
                # rule rollout may be provided as 'rollout' or numeric; normalize to int percentage
                rule_rollout = r.get("rollout")
                try:
                    roll_pct = int(rule_rollout) if rule_rollout is not None else 100
                except Exception:
                    # if rollout is a dict (like {'percentage': 50}), extract percentage
                    try:
                        roll_pct = int((rule_rollout or {}).get("percentage", 100))
                    except Exception as e2:
                        logger.debug(
                            "feature_rule_rollout_parse_failed",
                            extra={"rule_rollout": rule_rollout, "error": str(e2)},
                        )
                        roll_pct = 100
                self.rules.append(
                    FeatureFlagRule(
                        id=r.get("id"),
                        conditions=conds,
                        value=r.get("value"),
                        rollout=roll_pct,
                    )
                )
        ro = FeatureFlagRollout(**(rollout or {}))
        self.rollout = ro

    def evaluate(self, context: FeatureFlagContext) -> Tuple[Any, bool]:
        # - if not enabled -> return default_value, False
        if not self.is_enabled:
            return self.default_value, False

        # check rules
        for r in self.rules:
            # rules have their own rollout and value
            if r.evaluate(context):
                return r.value, True

        # check flag-level rollout
        if is_in_rollout(context.user_id, self.rollout.percentage):
            return self.enabled_value, True

        return self.default_value, False
