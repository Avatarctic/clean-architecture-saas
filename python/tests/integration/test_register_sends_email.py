import uuid

import pytest
from httpx import ASGITransport, AsyncClient


class SpySender:
    def __init__(self):
        self.calls = []

    async def send_verification(self, to_email: str, token: str):
        self.calls.append((to_email, token))

    async def send_password_reset(self, to_email: str, token: str):
        self.calls.append((to_email, token))


@pytest.mark.anyio(backends=["asyncio"])
async def test_resend_verification_triggers_email(test_app):
    """Test that resend-verification endpoint sends emails correctly."""
    client, engine, AsyncSessionLocal = test_app

    # Create a user directly via service layer (since /register no longer exists)
    from tests.conftest import create_tenant_and_user_direct

    unique = uuid.uuid4().hex
    tenant_name = f"t-{unique}"
    email = f"{unique}@example.com"

    await create_tenant_and_user_direct(AsyncSessionLocal, tenant_name, email, "pass123", "admin")

    sender = SpySender()

    # override dependency
    async def _get_sender():
        return sender

    from src.app.deps import get_email_sender

    client.app.dependency_overrides = {get_email_sender: _get_sender}

    async with AsyncClient(
        transport=ASGITransport(app=client.app), base_url="http://testserver"
    ) as ac:
        # Test resend-verification endpoint
        resp = await ac.post(
            "/api/v1/auth/resend-verification",
            json={"email": email},
        )
        assert resp.status_code == 200

    # Verify email was sent
    assert len(sender.calls) == 1
    assert sender.calls[0][0] == email  # to_email
    assert len(sender.calls[0][1]) > 0  # token
