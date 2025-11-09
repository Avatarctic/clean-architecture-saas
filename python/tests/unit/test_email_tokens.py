import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.app.domain.tenant import Tenant
from src.app.infrastructure.cache.redis_client import InMemoryCache
from src.app.infrastructure.db.models import Base
from src.app.infrastructure.repositories import get_repositories
from src.app.services.email_token_service import EmailTokenService


@pytest.mark.asyncio
async def test_email_token_create_consume():
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        # Email tokens require cache
        cache = InMemoryCache()
        repos = get_repositories(session, cache=cache)
        tenant_repo = repos["tenants"]
        t = Tenant(id=None, name="t1")
        await tenant_repo.create(t)
        # create user
        from src.app.domain.user import User

        user = User(
            id=None,
            tenant_id=1,
            email="u@example.com",
            hashed_password="x",
            is_active=True,
        )
        user_repo = repos["users"]
        created = await user_repo.create(user)

        # Use email_tokens repo
        email_tokens_repo = repos["email_tokens"]
        assert email_tokens_repo is not None, "email_tokens repo should be available with cache"

        svc = EmailTokenService(email_tokens_repo)
        token = await svc.create_token(created.id, "verification")
        assert token is not None
        info = await svc.consume_token(token)
        assert info["user_id"] == created.id
        assert info["purpose"] == "verification"
