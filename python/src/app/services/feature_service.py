from typing import Any, Dict, List, Optional

from ..domain.audit import AuditAction, AuditEvent, AuditResource
from ..domain.feature import FeatureFlag as DomainFeatureFlag
from ..domain.feature import FeatureFlagContext
from ..ports.audit import AuditRepository
from ..ports.cache import CacheClient
from ..ports.repositories import FeatureFlagRepository


class FeatureFlagService:
    def __init__(
        self,
        repo: FeatureFlagRepository,
        audit: Optional[AuditRepository] = None,
        cache: Optional[CacheClient] = None,
    ):
        self.repo = repo
        # accept the audit repository protocol directly to reduce coupling
        self.audit = audit
        self.cache = cache

    async def create_feature_flag(
        self,
        tenant_id: Optional[int],
        key: str,
        name: str,
        description: Optional[str],
        is_enabled: bool,
        type: str = "boolean",
        enabled_value: Optional[dict] = None,
        default_value: Optional[dict] = None,
        rules: Optional[list] = None,
        rollout: Optional[dict] = None,
        actor_user: Optional[dict] = None,
        current_tenant: Optional[object] = None,
    ) -> dict:
        ff = await self.repo.create(
            tenant_id,
            key,
            name,
            description,
            is_enabled,
            type=type,
            enabled_value=enabled_value,
            default_value=default_value,
            rules=rules,
            rollout=rollout,
        )
        # audit (use repository protocol)
        if self.audit:
            # prefer provided actor_user and tenant context
            cu = actor_user or {}
            ct = current_tenant if current_tenant is not None else {"id": tenant_id}
            event = AuditEvent(
                action=AuditAction.CREATE,
                resource=AuditResource.FEATURE_FLAG,
                resource_id=ff.get("id") if isinstance(ff, dict) else None,
                details={"key": key, "is_enabled": is_enabled},
            )
            await self.audit.log_event(cu, ct, event)
        # cache invalidation
        if self.cache:
            # cache a serialized boolean for fast path lookups; service/getters still return full dict
            await self.cache.set(f"feature:{tenant_id}:{key}", str(is_enabled))
        return ff

    async def get_feature_by_key(self, tenant_id: Optional[int], key: str) -> Optional[dict]:
        # try cache first
        if self.cache:
            val = await self.cache.get(f"feature:{tenant_id}:{key}")
            if val is not None:
                # cached value may be a minimal boolean; when used for evaluation we need full flag
                # if cache stored full serialized dict, return it
                if isinstance(val, dict):
                    return val
                # otherwise continue to repo fetch to get full record
        ff = await self.repo.get_by_key(tenant_id, key)
        return ff

    def _build_domain_flag(self, ff: Dict[str, Any]) -> DomainFeatureFlag:
        # repository returns dict with keys matching DB columns
        return DomainFeatureFlag(
            id=ff.get("id"),
            name=ff.get("name") or "",
            key=ff.get("key") or "",
            description=ff.get("description"),
            type=ff.get("type") or "boolean",
            is_enabled=ff.get("is_enabled") or False,
            enabled_value=ff.get("enabled_value"),
            default_value=ff.get("default_value"),
            rules=ff.get("rules"),
            rollout=ff.get("rollout"),
        )

    async def is_feature_enabled(
        self,
        tenant_id: Optional[int],
        key: str,
        user_id: Optional[int | str | None] = None,
        custom: Optional[dict] = None,
        role: Optional[str] = None,
        plan: Optional[str] = None,
    ) -> bool:
        f = await self.get_feature_by_key(tenant_id, key)
        if not f:
            # Record metric for missing feature flag
            try:
                from ..metrics import FEATURE_FLAG_EVALUATIONS

                if FEATURE_FLAG_EVALUATIONS is not None:
                    FEATURE_FLAG_EVALUATIONS.labels(key=key, result="disabled").inc()
            except Exception:
                pass
            return False
        domain = self._build_domain_flag(f)
        ctx = FeatureFlagContext(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            plan=plan,
            custom=custom or {},
        )
        _, enabled = domain.evaluate(ctx)

        # Record metric for feature flag evaluation
        try:
            from ..metrics import FEATURE_FLAG_EVALUATIONS

            result = "enabled" if enabled else "disabled"
            if FEATURE_FLAG_EVALUATIONS is not None:
                FEATURE_FLAG_EVALUATIONS.labels(key=key, result=result).inc()
        except Exception:
            pass

        return bool(enabled)

    async def get_feature_value(
        self,
        tenant_id: Optional[int],
        key: str,
        user_id: Optional[int | str | None] = None,
        custom: Optional[dict] = None,
        role: Optional[str] = None,
        plan: Optional[str] = None,
    ) -> Any:
        f = await self.get_feature_by_key(tenant_id, key)
        if not f:
            return None
        domain = self._build_domain_flag(f)
        ctx = FeatureFlagContext(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            plan=plan,
            custom=custom or {},
        )
        val, _ = domain.evaluate(ctx)
        return val

    async def list_feature_flags(
        self, tenant_id: Optional[int], limit: int = 50, offset: int = 0
    ) -> List[dict]:
        return await self.repo.list(tenant_id, limit, offset)

    async def update_feature_flag(
        self,
        id: int,
        actor_user: Optional[dict] = None,
        current_tenant: Optional[object] = None,
        **fields,
    ) -> dict:
        ff = await self.repo.update(id, **fields)
        if self.audit:
            cu = actor_user or {}
            ct = current_tenant if current_tenant is not None else {"id": ff.get("tenant_id")}
            event = AuditEvent(
                action=AuditAction.UPDATE,
                resource=AuditResource.FEATURE_FLAG,
                resource_id=id,
                details={"id": id, "fields": fields},
            )
            await self.audit.log_event(cu, ct, event)
        if self.cache:
            # invalidate potential cache entries
            key = ff.get("key")
            await self.cache.set(f"feature:{ff.get('tenant_id')}:{key}", str(ff.get("is_enabled")))
        return ff

    async def delete_feature_flag(
        self,
        id: int,
        actor_user: Optional[dict] = None,
        current_tenant: Optional[object] = None,
    ) -> None:
        ff = await self.repo.get_by_id(id)
        await self.repo.delete(id)
        if self.audit:
            cu = actor_user or {}
            ct = (
                current_tenant
                if current_tenant is not None
                else {"id": ff.get("tenant_id") if ff else None}
            )
            event = AuditEvent(
                action=AuditAction.DELETE,
                resource=AuditResource.FEATURE_FLAG,
                resource_id=id,
                details={"id": id, "key": ff.get("key") if isinstance(ff, dict) else None},
            )
            await self.audit.log_event(cu, ct, event)
        if self.cache and ff:
            await self.cache.set(f"feature:{ff.get('tenant_id')}:{ff.get('key')}", "False")
