"""Unit tests for TenantService state transitions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.app.domain.tenant import Tenant
from src.app.infrastructure.db.models import Base
from src.app.infrastructure.repositories import get_repositories
from src.app.services.tenant_service import TenantService


@pytest.mark.asyncio
async def test_suspend_tenant_from_active():
    """Test suspending an active tenant."""
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        # Create active tenant
        tenant = Tenant(id=None, name="test_tenant", status="active")
        created = await tenant_repo.create(tenant)

        # Suspend tenant
        service = TenantService(tenant_repo)
        suspended = await service.suspend_tenant(created.id)

        assert suspended.status == "suspended"
        assert suspended.id == created.id


@pytest.mark.asyncio
async def test_suspend_tenant_from_trial():
    """Test that suspending a tenant in trial status fails (not allowed by domain logic)."""
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        # Create trial tenant
        tenant = Tenant(id=None, name="trial_tenant", status="trial")
        created = await tenant_repo.create(tenant)

        # Try to suspend tenant (should fail - trial not in allowed transitions)
        service = TenantService(tenant_repo)
        with pytest.raises(ValueError, match="Cannot suspend tenant"):
            await service.suspend_tenant(created.id)


@pytest.mark.asyncio
async def test_suspend_canceled_tenant_fails():
    """Test that suspending a canceled tenant fails."""
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        # Create canceled tenant
        tenant = Tenant(id=None, name="canceled_tenant", status="canceled")
        created = await tenant_repo.create(tenant)

        # Try to suspend canceled tenant
        service = TenantService(tenant_repo)
        with pytest.raises(ValueError, match="Cannot suspend tenant"):
            await service.suspend_tenant(created.id)


@pytest.mark.asyncio
async def test_activate_tenant_from_suspended():
    """Test activating a suspended tenant."""
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        # Create suspended tenant
        tenant = Tenant(id=None, name="susp_tenant", status="suspended")
        created = await tenant_repo.create(tenant)

        # Activate tenant
        service = TenantService(tenant_repo)
        activated = await service.activate_tenant(created.id)

        assert activated.status == "active"


@pytest.mark.asyncio
async def test_activate_tenant_from_trial():
    """Test that activating a tenant from trial status fails (not allowed by domain logic)."""
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        # Create trial tenant
        tenant = Tenant(id=None, name="trial_tenant2", status="trial")
        created = await tenant_repo.create(tenant)

        # Try to activate tenant (should fail - trial not in allowed transitions)
        service = TenantService(tenant_repo)
        with pytest.raises(ValueError, match="Cannot activate tenant"):
            await service.activate_tenant(created.id)


@pytest.mark.asyncio
async def test_activate_canceled_tenant_fails():
    """Test that activating a canceled tenant fails."""
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        # Create canceled tenant
        tenant = Tenant(id=None, name="canceled_tenant2", status="canceled")
        created = await tenant_repo.create(tenant)

        # Try to activate canceled tenant
        service = TenantService(tenant_repo)
        with pytest.raises(ValueError, match="Cannot activate tenant"):
            await service.activate_tenant(created.id)


@pytest.mark.asyncio
async def test_cancel_tenant_from_active():
    """Test canceling an active tenant."""
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        # Create active tenant
        tenant = Tenant(id=None, name="active_cancel", status="active")
        created = await tenant_repo.create(tenant)

        # Cancel tenant
        service = TenantService(tenant_repo)
        canceled = await service.cancel_tenant(created.id)

        assert canceled.status == "canceled"


@pytest.mark.asyncio
async def test_cancel_tenant_from_suspended():
    """Test canceling a suspended tenant."""
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        # Create suspended tenant
        tenant = Tenant(id=None, name="susp_cancel", status="suspended")
        created = await tenant_repo.create(tenant)

        # Cancel tenant
        service = TenantService(tenant_repo)
        canceled = await service.cancel_tenant(created.id)

        assert canceled.status == "canceled"


@pytest.mark.asyncio
async def test_cancel_already_canceled_tenant_fails():
    """Test that canceling an already canceled tenant fails."""
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        # Create canceled tenant
        tenant = Tenant(id=None, name="already_canceled", status="canceled")
        created = await tenant_repo.create(tenant)

        # Try to cancel again
        service = TenantService(tenant_repo)
        with pytest.raises(ValueError, match="Cannot cancel tenant"):
            await service.cancel_tenant(created.id)


@pytest.mark.asyncio
async def test_suspend_nonexistent_tenant_fails():
    """Test that suspending a nonexistent tenant fails."""
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        # Try to suspend nonexistent tenant
        service = TenantService(tenant_repo)
        with pytest.raises(ValueError, match="Tenant not found"):
            await service.suspend_tenant(99999)


@pytest.mark.asyncio
async def test_activate_nonexistent_tenant_fails():
    """Test that activating a nonexistent tenant fails."""
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        # Try to activate nonexistent tenant
        service = TenantService(tenant_repo)
        with pytest.raises(ValueError, match="Tenant not found"):
            await service.activate_tenant(99999)


@pytest.mark.asyncio
async def test_cancel_nonexistent_tenant_fails():
    """Test that canceling a nonexistent tenant fails."""
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]

        # Try to cancel nonexistent tenant
        service = TenantService(tenant_repo)
        with pytest.raises(ValueError, match="Tenant not found"):
            await service.cancel_tenant(99999)
