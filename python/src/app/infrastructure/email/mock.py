import asyncio


class MockEmailSender:
    def __init__(self):
        self.sent = []

    async def send_verification(self, to_email: str, token: str) -> None:
        # simulate async send
        await asyncio.sleep(0)
        self.sent.append({"type": "verification", "to": to_email, "token": token})

    async def send_password_reset(self, to_email: str, token: str) -> None:
        await asyncio.sleep(0)
        self.sent.append({"type": "password_reset", "to": to_email, "token": token})
