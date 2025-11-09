from typing import Any, Dict, List, Optional

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import models


class SqlAlchemyPermissionRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_role(self, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        m = models.RoleModel(name=name, description=description)
        self.db_session.add(m)
        await self.db_session.flush()
        return {"id": int(m.id), "name": m.name, "description": m.description}

    async def create_permission(
        self, name: str, description: Optional[str] = None
    ) -> Dict[str, Any]:
        m = models.PermissionModel(name=name, description=description)
        self.db_session.add(m)
        await self.db_session.flush()
        return {"id": int(m.id), "name": m.name, "description": m.description}

    async def get_role_by_name(self, name: str):
        q = await self.db_session.execute(
            select(models.RoleModel).where(models.RoleModel.name == name)
        )
        return q.scalars().first()

    async def get_permission_by_name(self, name: str):
        q = await self.db_session.execute(
            select(models.PermissionModel).where(models.PermissionModel.name == name)
        )
        return q.scalars().first()

    async def get_permissions_by_names(self, names: List[str]) -> List[Dict[str, Any]]:
        """Bulk fetch permissions by names to avoid N+1 queries."""
        if not names:
            return []
        q = await self.db_session.execute(
            select(models.PermissionModel).where(models.PermissionModel.name.in_(names))
        )
        rows = q.scalars().all()
        return [{"id": int(p.id), "name": p.name, "description": p.description} for p in rows]

    async def list_permissions(self) -> List[Dict[str, Any]]:
        """List all available permissions in the system."""
        q = await self.db_session.execute(select(models.PermissionModel))
        rows = q.scalars().all()
        return [{"id": int(p.id), "name": p.name, "description": p.description} for p in rows]

    async def list_role_permissions(self, role_id: int) -> List[Dict[str, Any]]:
        """List all permissions assigned to a role."""
        rp = models.role_permissions
        q = await self.db_session.execute(
            select(models.PermissionModel)
            .select_from(
                rp.join(
                    models.PermissionModel,
                    rp.c.permission_id == models.PermissionModel.id,
                )
            )
            .where(rp.c.role_id == role_id)
        )
        rows = q.scalars().all()
        return [{"id": int(p.id), "name": p.name, "description": p.description} for p in rows]

    async def clear_role_permissions(self, role_id: int) -> None:
        """Clear all permissions from a role."""
        rp = models.role_permissions
        await self.db_session.execute(delete(rp).where(rp.c.role_id == role_id))
        await self.db_session.flush()

    async def assign_permission_to_role(self, role_id: int, permission_id: int) -> None:
        # insert into association table if not exists
        # check exists
        rp = models.role_permissions
        q = await self.db_session.execute(
            select(rp).where(rp.c.role_id == role_id, rp.c.permission_id == permission_id)
        )
        if q.first():
            return
        await self.db_session.execute(
            insert(rp).values(role_id=role_id, permission_id=permission_id)
        )
        await self.db_session.flush()

    async def bulk_assign_permissions_to_role(
        self, role_id: int, permission_ids: List[int]
    ) -> None:
        """Bulk assign permissions to a role, avoiding N+1 queries."""
        if not permission_ids:
            return

        rp = models.role_permissions
        # Get existing associations to avoid duplicates
        q = await self.db_session.execute(select(rp.c.permission_id).where(rp.c.role_id == role_id))
        existing_perm_ids = {row[0] for row in q.all()}

        # Filter out permissions that already exist
        new_perm_ids = [pid for pid in permission_ids if pid not in existing_perm_ids]

        if new_perm_ids:
            # Bulk insert new associations
            values = [{"role_id": role_id, "permission_id": pid} for pid in new_perm_ids]
            await self.db_session.execute(insert(rp).values(values))
            await self.db_session.flush()

    async def remove_permission_from_role(self, role_id: int, permission_id: int) -> None:
        rp = models.role_permissions
        await self.db_session.execute(
            delete(rp).where(rp.c.role_id == role_id, rp.c.permission_id == permission_id)
        )
        await self.db_session.flush()

    async def list_user_permissions(self, user_id: int) -> List[str]:
        # fetch user, read its role string and evaluate permissions for that role
        q = await self.db_session.execute(
            select(models.UserModel).where(models.UserModel.id == user_id)
        )
        u = q.scalars().first()
        if not u:
            return []
        role = getattr(u, "role", None)
        return await self.get_role_permissions(role or "")

    async def get_role_permissions(self, role: str) -> List[str]:
        if not role:
            return []
        # join role_permissions -> permissions to return permission names
        rp = models.role_permissions
        q = await self.db_session.execute(
            select(models.PermissionModel.name)
            .select_from(
                rp.join(
                    models.PermissionModel,
                    rp.c.permission_id == models.PermissionModel.id,
                ).join(models.RoleModel, rp.c.role_id == models.RoleModel.id)
            )
            .where(models.RoleModel.name == role)
        )
        rows = q.all()
        return [r[0] for r in rows]

    async def set_role_permissions(self, role, permissions) -> None:
        # find or create role
        q = await self.db_session.execute(
            select(models.RoleModel).where(models.RoleModel.name == role)
        )
        r = q.scalars().first()
        if not r:
            r = models.RoleModel(name=role)
            self.db_session.add(r)
            await self.db_session.flush()
        # clear existing associations
        rp = models.role_permissions
        await self.db_session.execute(delete(rp).where(rp.c.role_id == r.id))
        # upsert permissions by name and associate
        for pname in permissions:
            pq = await self.db_session.execute(
                select(models.PermissionModel).where(models.PermissionModel.name == pname)
            )
            p = pq.scalars().first()
            if not p:
                p = models.PermissionModel(name=pname)
                self.db_session.add(p)
                await self.db_session.flush()
            await self.db_session.execute(insert(rp).values(role_id=r.id, permission_id=p.id))
        await self.db_session.flush()
