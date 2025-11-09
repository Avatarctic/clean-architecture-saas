import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.anyio
async def test_metrics_endpoint(test_app):
    client, engine, AsyncSessionLocal = test_app
    async with AsyncClient(transport=ASGITransport(app=client.app), base_url="http://test") as ac:
        resp = await ac.get("/metrics")
        assert resp.status_code == 200
        assert "http_requests_total" in resp.text
