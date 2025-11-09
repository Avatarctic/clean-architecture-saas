import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.app.domain.auth import TokenClaims
from src.app.domain.tenant import Tenant
from src.app.domain.user import User
from src.app.infrastructure.db.models import Base
from src.app.infrastructure.repositories import get_repositories
from src.app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_refresh_token_flow():
    url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        repos = get_repositories(session, cache=None)
        tenant_repo = repos["tenants"]
        tokens_repo = repos["tokens"]
        user_repo = repos["users"]
        # create tenant
        t = Tenant(id=None, name="t1")
        await tenant_repo.create(t)
        # create user
        u = User(
            id=None,
            tenant_id=1,
            email="u@example.com",
            hashed_password="x",
            is_active=True,
        )
        created = await user_repo.create(u)
        auth = AuthService("secret")
        sid = auth.generate_session_id()
        rt = auth.generate_refresh_token()
        # Persist refresh token hash in DB (server-side identifier)
        token_hash = auth.hash_refresh_token(rt)
        await tokens_repo.create_refresh_token(created.id, token_hash)
        model = await tokens_repo.find_by_token_hash(token_hash)
        assert model is not None
        assert model.user_id == created.id
        # verify token creation
        claims = TokenClaims(
            subject=str(created.id),
            tenant_id=int(created.tenant_id) if created.tenant_id is not None else None,
            extra={"sid": sid},
        )
        token = auth.create_access_token(claims)
        assert token is not None
