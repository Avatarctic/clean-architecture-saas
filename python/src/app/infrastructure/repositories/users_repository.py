from typing import Any, List, Optional, cast

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.domain.user import User as DomainUser
from src.app.logging_config import get_logger

from ..db import models

logger = get_logger(__name__)


class SqlAlchemyUserRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create(self, user: DomainUser) -> DomainUser:
        logger.debug("creating_user", extra={"email": user.email, "tenant_id": user.tenant_id})
        m = models.UserModel(
            tenant_id=user.tenant_id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            hashed_password=user.hashed_password,
            role=user.role,
            email_verified=user.email_verified,
            audit_enabled=user.audit_enabled,
            last_login_at=user.last_login_at,
            is_active=user.is_active,
        )
        self.db_session.add(m)
        await self.db_session.flush()
        try:
            await self.db_session.commit()
            logger.info(
                "user_created",
                extra={"user_id": m.id, "email": user.email, "tenant_id": user.tenant_id},
            )
        except Exception as e:
            logger.exception(
                "user_create_commit_failed", extra={"error": str(e), "email": user.email}
            )
            raise  # Re-raise to prevent silent failure
        return DomainUser(
            id=int(m.id),
            tenant_id=int(m.tenant_id),
            first_name=cast(Any, m.first_name),
            last_name=cast(Any, m.last_name),
            email=cast(Any, m.email),
            hashed_password=cast(Any, m.hashed_password),
            role=cast(Any, m.role),
            email_verified=cast(Any, m.email_verified),
            audit_enabled=cast(Any, m.audit_enabled),
            last_login_at=cast(Any, m.last_login_at),
            is_active=cast(Any, m.is_active),
            created_at=cast(Any, m.created_at),
            updated_at=cast(Any, m.updated_at),
        )

    async def get_by_email(self, tenant_id: int, email: str) -> Optional[DomainUser]:
        q = await self.db_session.execute(
            select(models.UserModel).where(
                models.UserModel.tenant_id == tenant_id,
                models.UserModel.email == email,
            )
        )
        row = q.scalars().first()
        if not row:
            return None
        return DomainUser(
            id=int(row.id),
            tenant_id=int(row.tenant_id),
            first_name=cast(Any, row.first_name),
            last_name=cast(Any, row.last_name),
            email=cast(Any, row.email),
            hashed_password=cast(Any, row.hashed_password),
            role=cast(Any, row.role),
            email_verified=cast(Any, row.email_verified),
            audit_enabled=cast(Any, row.audit_enabled),
            last_login_at=cast(Any, row.last_login_at),
            is_active=cast(Any, row.is_active),
            created_at=cast(Any, row.created_at),
            updated_at=cast(Any, row.updated_at),
        )

    async def get_by_email_global(self, email: str) -> Optional[DomainUser]:
        """Find user by email across all tenants (for login)."""
        q = await self.db_session.execute(
            select(models.UserModel).where(models.UserModel.email == email)
        )
        row = q.scalars().first()
        if not row:
            return None
        return DomainUser(
            id=int(row.id),
            tenant_id=int(row.tenant_id),
            first_name=cast(Any, row.first_name),
            last_name=cast(Any, row.last_name),
            email=cast(Any, row.email),
            hashed_password=cast(Any, row.hashed_password),
            role=cast(Any, row.role),
            email_verified=cast(Any, row.email_verified),
            audit_enabled=cast(Any, row.audit_enabled),
            last_login_at=cast(Any, row.last_login_at),
            is_active=cast(Any, row.is_active),
            created_at=cast(Any, row.created_at),
            updated_at=cast(Any, row.updated_at),
        )

    async def get_by_id(self, id: int) -> Optional[DomainUser]:
        """Get user by ID.

        Note: Does not filter by tenant_id - tenant validation is enforced at
        middleware level (CurrentUserMiddleware) which verifies user.tenant_id
        matches the resolved tenant before request proceeds. This repository
        method is also used for fetching the current authenticated user.
        """
        q = await self.db_session.execute(select(models.UserModel).where(models.UserModel.id == id))
        row = q.scalars().first()
        if not row:
            return None
        return DomainUser(
            id=int(row.id),
            tenant_id=int(row.tenant_id),
            first_name=cast(Any, row.first_name),
            last_name=cast(Any, row.last_name),
            email=cast(Any, row.email),
            hashed_password=cast(Any, row.hashed_password),
            role=cast(Any, row.role),
            email_verified=cast(Any, row.email_verified),
            audit_enabled=cast(Any, row.audit_enabled),
            last_login_at=cast(Any, row.last_login_at),
            is_active=cast(Any, row.is_active),
            created_at=cast(Any, row.created_at),
            updated_at=cast(Any, row.updated_at),
        )

    async def list_by_tenant(self, tenant_id: int) -> List[DomainUser]:
        q = await self.db_session.execute(
            select(models.UserModel).where(models.UserModel.tenant_id == tenant_id)
        )
        rows = q.scalars().all()
        return [
            DomainUser(
                id=int(r.id),
                tenant_id=int(r.tenant_id),
                first_name=cast(Any, r.first_name),
                last_name=cast(Any, r.last_name),
                email=cast(Any, r.email),
                hashed_password=cast(Any, r.hashed_password),
                role=cast(Any, r.role),
                email_verified=cast(Any, r.email_verified),
                audit_enabled=cast(Any, r.audit_enabled),
                last_login_at=cast(Any, r.last_login_at),
                is_active=cast(Any, r.is_active),
                created_at=cast(Any, r.created_at),
                updated_at=cast(Any, r.updated_at),
            )
            for r in rows
        ]

    async def delete(self, id: int) -> None:
        await self.db_session.execute(delete(models.UserModel).where(models.UserModel.id == id))
        await self.db_session.flush()

    async def update(self, id: int, **fields) -> Optional[DomainUser]:
        """Update a user's mutable fields using an explicit whitelist.

        This prevents accidental updates to sensitive fields like email and
        hashed_password. Allowed fields: first_name, last_name, role,
        is_active, email_verified, audit_enabled.
        Returns the updated DomainUser or None if not found.
        """
        allowed = {
            "first_name",
            "last_name",
            "role",
            "is_active",
            "email_verified",
            "audit_enabled",
        }
        update_fields = {k: v for k, v in fields.items() if k in allowed}
        if not update_fields:
            return await self.get_by_id(id)
        # ensure updated_at is set
        from datetime import datetime

        update_fields["updated_at"] = datetime.utcnow()
        await self.db_session.execute(
            update(models.UserModel).where(models.UserModel.id == id).values(**update_fields)
        )
        await self.db_session.flush()
        return await self.get_by_id(id)

    async def set_password(self, user_id: int, hashed_password: str) -> None:
        """Explicit API to set a user's password (for password reset)."""
        from datetime import datetime

        await self.db_session.execute(
            update(models.UserModel)
            .where(models.UserModel.id == user_id)
            .values(hashed_password=hashed_password, updated_at=datetime.utcnow())
        )
        await self.db_session.flush()

    async def update_last_login(self, user_id: int, when) -> None:
        """Set last_login_at for the user to `when`. This is the only place
        that should update last_login_at (called from auth/login flow)."""
        from datetime import datetime

        # accept naive or aware datetimes; persist as-is
        await self.db_session.execute(
            update(models.UserModel)
            .where(models.UserModel.id == user_id)
            .values(last_login_at=when, updated_at=datetime.utcnow())
        )
        await self.db_session.flush()

    async def set_email(self, user_id: int, new_email: str) -> None:
        """Explicit API to set a user's email (used by email-change confirmation)."""
        from datetime import datetime

        await self.db_session.execute(
            update(models.UserModel)
            .where(models.UserModel.id == user_id)
            .values(email=new_email, email_verified=True, updated_at=datetime.utcnow())
        )
        await self.db_session.flush()
