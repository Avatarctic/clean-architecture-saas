import pytest

from src.app.domain.audit import AuditAction, AuditEvent
from src.app.infrastructure.db import models
from src.app.infrastructure.repositories.audit_repository import (
    SqlAlchemyAuditRepository,
)


@pytest.mark.asyncio
async def test_audit_not_written_when_user_disabled(test_app):
    """If a user's audit_enabled is False, no audit row should be persisted."""
    client, engine, AsyncSessionLocal = test_app

    async with AsyncSessionLocal() as session:
        # create tenant
        tenant = models.TenantModel(name="t1", slug="t1")
        session.add(tenant)
        await session.flush()

        # create user with audit_enabled = False
        user = models.UserModel(
            tenant_id=tenant.id,
            email="u1@example.com",
            hashed_password="x",
            audit_enabled=False,
        )
        session.add(user)
        await session.flush()

        repo = SqlAlchemyAuditRepository(session)
        current_user = {
            "id": int(user.id),
            "audit_enabled": getattr(user, "audit_enabled", None),
        }
        current_tenant = {"id": int(tenant.id)}
        event = AuditEvent(action=AuditAction.UPDATE, details={"k": "v"})
        await repo.log_event(current_user, current_tenant, event)

        # query audit events
        q = await session.execute(models.AuditModel.__table__.select())
        rows = q.fetchall()
        assert len(rows) == 0


@pytest.mark.asyncio
async def test_audit_written_when_user_enabled(test_app):
    """If a user's audit_enabled is True, an audit row should be persisted."""
    client, engine, AsyncSessionLocal = test_app

    async with AsyncSessionLocal() as session:
        # create tenant
        tenant = models.TenantModel(name="t2", slug="t2")
        session.add(tenant)
        await session.flush()

        # create user with audit_enabled = True
        user = models.UserModel(
            tenant_id=tenant.id,
            email="u2@example.com",
            hashed_password="x",
            audit_enabled=True,
        )
        session.add(user)
        await session.flush()

        repo = SqlAlchemyAuditRepository(session)
        current_user = {
            "id": int(user.id),
            "audit_enabled": getattr(user, "audit_enabled", None),
        }
        current_tenant = {"id": int(tenant.id)}
        event = AuditEvent(action=AuditAction.UPDATE, details={"k": "v"})
        await repo.log_event(current_user, current_tenant, event)

        # query audit events
        q = await session.execute(models.AuditModel.__table__.select())
        rows = q.fetchall()
        assert len(rows) == 1
        # basic content checks
        row = rows[0]
        assert row._mapping["action"] == AuditAction.UPDATE.value
        assert row._mapping["user_id"] == user.id
