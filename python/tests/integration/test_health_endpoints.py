"""Integration tests for health endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok(test_app):
    """Test that /health endpoint returns ok status."""
    client, engine, AsyncSessionLocal = test_app

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        resp = await http.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"status": "ok"}


@pytest.mark.asyncio
async def test_api_v1_health_endpoint_returns_ok(test_app):
    """Test that /api/v1/health endpoint returns ok status."""
    client, engine, AsyncSessionLocal = test_app

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        resp = await http.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_endpoint_no_auth_required(test_app):
    """Test that health endpoints don't require authentication."""
    client, engine, AsyncSessionLocal = test_app

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        # Call without any authorization header
        resp = await http.get("/health")
        assert resp.status_code == 200

        resp = await http.get("/api/v1/health")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoints_are_fast(test_app):
    """Test that health endpoints respond quickly (important for monitoring)."""
    import time

    client, engine, AsyncSessionLocal = test_app

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as http:
        start = time.time()
        resp = await http.get("/health")
        elapsed = time.time() - start

        assert resp.status_code == 200
        # Health check should complete in under 1 second
        assert elapsed < 1.0, f"Health check took {elapsed}s, should be < 1s"
