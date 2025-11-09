from typing import Any, List, Optional, cast

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.domain.tenant import Tenant as DomainTenant

from ..db import models


class SqlAlchemyTenantRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self._tokens = None
        self._cache = None

    async def create(self, tenant: DomainTenant) -> DomainTenant:
        m = models.TenantModel(
            name=tenant.name,
            slug=getattr(tenant, "slug", None),
            domain=getattr(tenant, "domain", None),
            plan=getattr(tenant, "plan", "free"),
            status=getattr(tenant, "status", "active"),
            settings=getattr(tenant, "settings", {}) or {},
        )
        self.db_session.add(m)
        await self.db_session.flush()
        try:
            await self.db_session.commit()
        except Exception as e:
            try:
                from ..logging_config import get_logger

                get_logger(__name__).debug("tenant_create_commit_failed", extra={"error": str(e)})
            except Exception:
                # best-effort: don't raise from logging failure
                pass
            raise  # Re-raise to prevent silent failure
        return DomainTenant(
            id=int(m.id),
            name=cast(Any, m.name),
            slug=cast(Any, m.slug),
            domain=cast(Any, m.domain),
            plan=cast(Any, m.plan),
            status=cast(Any, m.status),
            settings=cast(Any, m.settings),
            created_at=cast(Any, m.created_at),
            updated_at=cast(Any, m.updated_at),
        )

    async def get_by_id(self, id: int) -> Optional[DomainTenant]:
        q = await self.db_session.execute(
            select(models.TenantModel).where(models.TenantModel.id == id)
        )
        row = q.scalars().first()
        if not row:
            return None
        return DomainTenant(
            id=int(row.id),
            name=cast(Any, row.name),
            slug=cast(Any, getattr(row, "slug", None)),
            domain=cast(Any, getattr(row, "domain", None)),
            plan=cast(Any, getattr(row, "plan", "free")),
            status=cast(Any, getattr(row, "status", "active")),
            settings=cast(Any, getattr(row, "settings", {})),
            created_at=cast(Any, row.created_at),
            updated_at=cast(Any, row.updated_at),
        )

    async def list(self) -> List[DomainTenant]:
        q = await self.db_session.execute(select(models.TenantModel))
        rows = q.scalars().all()
        return [
            DomainTenant(
                id=int(r.id),
                name=cast(Any, r.name),
                slug=cast(Any, getattr(r, "slug", None)),
                domain=cast(Any, getattr(r, "domain", None)),
                plan=cast(Any, getattr(r, "plan", "free")),
                status=cast(Any, getattr(r, "status", "active")),
                settings=cast(Any, getattr(r, "settings", {})),
                created_at=cast(Any, r.created_at),
                updated_at=cast(Any, r.updated_at),
            )
            for r in rows
        ]

    async def list_all(self) -> List[DomainTenant]:
        """Return all tenants. Alias for list() method."""
        return await self.list()

    async def get_by_slug(self, slug: str) -> Optional[DomainTenant]:
        q = await self.db_session.execute(
            select(models.TenantModel).where(models.TenantModel.slug == slug)
        )
        row = q.scalars().first()
        if not row:
            return None
        return DomainTenant(
            id=int(row.id),
            name=cast(Any, row.name),
            slug=cast(Any, getattr(row, "slug", None)),
            domain=cast(Any, getattr(row, "domain", None)),
            plan=cast(Any, getattr(row, "plan", "free")),
            status=cast(Any, getattr(row, "status", "active")),
            settings=cast(Any, getattr(row, "settings", {})),
            created_at=cast(Any, row.created_at),
            updated_at=cast(Any, row.updated_at),
        )

    async def update(self, id: int, **fields) -> Optional[DomainTenant]:
        allowed = {"name", "domain", "is_active", "status", "plan", "settings"}
        update_fields = {k: v for k, v in fields.items() if k in allowed}
        if not update_fields:
            return await self.get_by_id(id)
        from datetime import datetime

        update_fields["updated_at"] = datetime.utcnow()
        await self.db_session.execute(
            update(models.TenantModel).where(models.TenantModel.id == id).values(**update_fields)
        )
        await self.db_session.flush()
        return await self.get_by_id(id)

    async def update_status(self, id: int, status: str) -> Optional[DomainTenant]:
        """Update tenant status."""
        return await self.update(id, status=status)

    async def delete(self, id: int) -> None:
        await self.db_session.execute(delete(models.TenantModel).where(models.TenantModel.id == id))
        await self.db_session.flush()
