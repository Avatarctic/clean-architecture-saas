from typing import Protocol


class EmailSender(Protocol):
    """Protocol for email sending operations."""

    async def send_verification(self, to_email: str, token: str) -> None: ...
    async def send_password_reset(self, to_email: str, token: str) -> None: ...
