from typing import Optional, Protocol


class EmailTokenRepository(Protocol):
    """Protocol for email token repository operations."""

    async def create_token(
        self, user_id: int, token: str, purpose: str, data: dict | None = None, ttl: int = 3600
    ) -> None: ...

    async def consume_token(self, token: str) -> Optional[dict]: ...
