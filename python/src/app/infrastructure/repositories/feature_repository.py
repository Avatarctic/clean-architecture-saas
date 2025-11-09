from typing import Any, Dict, List, Optional, cast

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import models


class SqlAlchemyFeatureFlagRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create(
        self,
        tenant_id: int | None,
        key: str,
        name: str,
        description: Optional[str],
        is_enabled: bool,
        type: str = "boolean",
        enabled_value: dict | None = None,
        default_value: dict | None = None,
        rules: list | None = None,
        rollout: dict | None = None,
    ) -> Dict[str, Any]:
        m = models.FeatureFlagModel(
            tenant_id=tenant_id,
            key=key,
            name=name or key,
            description=description,
            type=type,
            is_enabled=bool(is_enabled),
            enabled_value=enabled_value,
            default_value=default_value,
            rules=(rules or []),
            rollout=(rollout or {"percentage": 100, "strategy": "random"}),
        )
        self.db_session.add(m)
        await self.db_session.flush()
        try:
            await self.db_session.commit()
        except Exception as e:
            try:
                from ..logging_config import get_logger

                get_logger(__name__).debug("feature_create_commit_failed", extra={"error": str(e)})
            except Exception:
                # swallow logging failures
                pass
            raise  # Re-raise to prevent silent failure
        return {
            "id": int(m.id),
            "tenant_id": int(m.tenant_id) if m.tenant_id is not None else None,
            "key": cast(Any, m.key),
            "name": cast(Any, m.name),
            "description": cast(Any, m.description),
            "type": cast(Any, m.type),
            "is_enabled": cast(Any, m.is_enabled),
            "enabled_value": cast(Any, m.enabled_value),
            "default_value": cast(Any, m.default_value),
            "rules": cast(Any, m.rules),
            "rollout": cast(Any, m.rollout),
            "created_at": cast(Any, m.created_at),
            "updated_at": cast(Any, m.updated_at),
        }

    async def get_by_id(self, id: int) -> Optional[Dict[str, Any]]:
        q = await self.db_session.execute(
            select(models.FeatureFlagModel).where(models.FeatureFlagModel.id == id)
        )
        row = q.scalars().first()
        if not row:
            return None
        return {
            "id": int(row.id),
            "tenant_id": int(row.tenant_id) if row.tenant_id is not None else None,
            "key": cast(Any, row.key),
            "name": cast(Any, row.name),
            "description": cast(Any, row.description),
            "type": cast(Any, row.type),
            "is_enabled": cast(Any, row.is_enabled),
            "enabled_value": cast(Any, row.enabled_value),
            "default_value": cast(Any, row.default_value),
            "rules": cast(Any, row.rules),
            "rollout": cast(Any, row.rollout),
            "created_at": cast(Any, row.created_at),
            "updated_at": cast(Any, row.updated_at),
        }

    async def get_by_key(self, tenant_id: int | None, key: str) -> Optional[Dict[str, Any]]:
        # tenant_id may be None for global flags
        if tenant_id is None:
            q = await self.db_session.execute(
                select(models.FeatureFlagModel)
                .where(models.FeatureFlagModel.tenant_id == None)  # noqa: E711
                .where(models.FeatureFlagModel.key == key)
            )
        else:
            q = await self.db_session.execute(
                select(models.FeatureFlagModel)
                .where(models.FeatureFlagModel.tenant_id == tenant_id)
                .where(models.FeatureFlagModel.key == key)
            )
        row = q.scalars().first()
        if not row:
            return None
        return {
            "id": int(row.id),
            "tenant_id": int(row.tenant_id) if row.tenant_id is not None else None,
            "key": cast(Any, row.key),
            "name": cast(Any, row.name),
            "description": cast(Any, row.description),
            "type": cast(Any, row.type),
            "is_enabled": cast(Any, row.is_enabled),
            "enabled_value": cast(Any, row.enabled_value),
            "default_value": cast(Any, row.default_value),
            "rules": cast(Any, row.rules),
            "rollout": cast(Any, row.rollout),
            "created_at": cast(Any, row.created_at),
            "updated_at": cast(Any, row.updated_at),
        }

    async def list(
        self, tenant_id: int | None, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        q = await self.db_session.execute(
            select(models.FeatureFlagModel)
            .where(models.FeatureFlagModel.tenant_id == tenant_id)
            .limit(limit)
            .offset(offset)
        )
        rows = q.scalars().all()
        return [
            {
                "id": int(r.id),
                "tenant_id": int(r.tenant_id) if r.tenant_id is not None else None,
                "key": cast(Any, r.key),
                "name": cast(Any, r.name),
                "description": cast(Any, r.description),
                "type": cast(Any, r.type),
                "is_enabled": cast(Any, r.is_enabled),
                "enabled_value": cast(Any, r.enabled_value),
                "default_value": cast(Any, r.default_value),
                "rules": cast(Any, r.rules),
                "rollout": cast(Any, r.rollout),
                "created_at": cast(Any, r.created_at),
                "updated_at": cast(Any, r.updated_at),
            }
            for r in rows
        ]

    async def update(self, id: int, **fields) -> Optional[Dict[str, Any]]:
        allowed = {
            "description",
            "is_enabled",
            "rules",
            "rollout",
            "name",
            "enabled_value",
            "default_value",
        }
        update_fields = {k: v for k, v in fields.items() if k in allowed}
        if not update_fields:
            return await self.get_by_id(id)
        from datetime import datetime

        update_fields["updated_at"] = datetime.utcnow()
        await self.db_session.execute(
            update(models.FeatureFlagModel)
            .where(models.FeatureFlagModel.id == id)
            .values(**update_fields)
        )
        await self.db_session.flush()
        return await self.get_by_id(id)

    async def delete(self, id: int) -> None:
        await self.db_session.execute(
            delete(models.FeatureFlagModel).where(models.FeatureFlagModel.id == id)
        )
        await self.db_session.flush()
