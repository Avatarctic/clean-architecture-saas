import secrets
from typing import Optional

from ..ports.repositories import EmailTokenRepository


class EmailTokenService:
    def __init__(self, repo: EmailTokenRepository):
        self.repo = repo

    def generate_token(self) -> str:
        return secrets.token_urlsafe(32)

    async def create_token(
        self, user_id: int, purpose: str, data: dict | None = None, ttl: int = 3600
    ) -> str:
        token = self.generate_token()
        await self.repo.create_token(user_id, token, purpose, data=data, ttl=ttl)
        return token

    async def create_email_verification_token(
        self, user_id: int, email: str, ttl: int = 3600
    ) -> str:
        """Create a token for email verification."""
        return await self.create_token(
            user_id, purpose="email_verification", data={"email": email}, ttl=ttl
        )

    async def create_email_update_token(self, user_id: int, new_email: str, ttl: int = 3600) -> str:
        """Create a token for email address update confirmation."""
        return await self.create_token(
            user_id, purpose="email_update", data={"new_email": new_email}, ttl=ttl
        )

    async def consume_token(self, token: str) -> Optional[dict]:
        return await self.repo.consume_token(token)
