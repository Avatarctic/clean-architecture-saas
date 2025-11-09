import pytest
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from src.app.infrastructure.db import models
from src.app.wiring import create_app


@pytest.mark.asyncio
async def test_unknown_tenant_returns_404(test_app):
    client_obj, engine, AsyncSessionLocal = test_app
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # make a request with a host that does not resolve to a tenant
        resp = await client.get("/api/v1/health", headers={"host": "nosuch.example.com"})
        # health endpoint is allowed even for unknown tenants (middleware skips only health)
        assert resp.status_code == 200

        # non-health path should return 404 for unknown tenant
        resp = await client.get("/api/v1/protected", headers={"host": "nosuch.example.com"})
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_suspended_tenant_returns_403(test_app):
    client_obj, engine, AsyncSessionLocal = test_app

    # create tenant suspended in DB
    async with AsyncSessionLocal() as session:
        t = models.TenantModel(name="s1", slug="s1", status="suspended")
        session.add(t)
        await session.commit()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # any non-health endpoint should be rejected with 403
        resp = await client.get("/api/v1/protected", headers={"host": "s1.example.com"})
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_canceled_tenant_returns_403(test_app):
    client_obj, engine, AsyncSessionLocal = test_app

    # create tenant canceled in DB
    async with AsyncSessionLocal() as session:
        t = models.TenantModel(name="c1", slug="c1", status="canceled")
        session.add(t)
        await session.commit()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # any non-health endpoint should be rejected with 403
        resp = await client.get("/api/v1/protected", headers={"host": "c1.example.com"})
        assert resp.status_code == 403
