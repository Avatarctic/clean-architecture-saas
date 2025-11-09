import os
import sys

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.anyio
async def test_startup_initializes_redis_and_sendgrid():
    # set env vars before importing app so Settings picks them up
    os.environ["REDIS_URL"] = "redis://127.0.0.1:6379"
    os.environ["SENDGRID_API_KEY"] = "test-sendgrid-key"

    # ensure fresh imports so module-level Settings() is recreated
    for mod in [
        "src.app.main",
        "src.app.config",
        "src.app.deps",
        "src.app.infrastructure.cache.redis_client",
        "src.app.infrastructure.email.sendgrid",
    ]:
        if mod in sys.modules:
            del sys.modules[mod]

    import src.app.deps as deps
    import src.app.main as main

    # run the ASGI startup by creating a test client (startup events run)
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://testserver"
    ) as client:
        # make a trivial request so startup completes
        r = await client.get("/health")
        assert r.status_code == 200

    # after startup, app.state should have the initialized clients
    cache_client = getattr(main.app.state, "cache_client", None)
    email_sender = getattr(main.app.state, "email_sender", None)

    assert cache_client is not None, "cache client not initialized on startup"
    assert email_sender is not None, "email sender not initialized on startup"

    # deps module should also have exported references
    assert getattr(deps, "_app_cache_client", None) is not None
    assert getattr(deps, "_app_email_sender", None) is not None
