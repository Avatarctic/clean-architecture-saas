import asyncio
from typing import Optional

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
except Exception as e:
    try:
        from ...logging_config import get_logger

        get_logger(__name__).debug("sendgrid_import_failed", extra={"error": str(e)})
    except Exception:
        pass
    SendGridAPIClient = None
    Mail = None

from ...config import Settings


class SendGridEmailSender:
    def __init__(self, api_key: Optional[str] = None, from_email: Optional[str] = None):
        s = Settings()
        self.api_key = api_key or s.sendgrid_api_key
        self.from_email = from_email or s.email_from
        if SendGridAPIClient is None:
            # will fail at runtime if used without package
            raise RuntimeError("sendgrid package is not installed")

    async def _send(self, to_email: str, subject: str, html_content: str) -> None:
        # SendGrid client is synchronous; wrap in thread via asyncio to avoid blocking event loop
        client = SendGridAPIClient(self.api_key)
        message = Mail(
            from_email=self.from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )
        # run in thread
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, client.send, message)

    async def send_verification(self, to_email: str, token: str) -> None:
        """Send account verification email containing a token link."""
        subject = "Verify your account"
        s = Settings()
        url = f"{s.frontend_url}/verify?token={token}"
        html = f'<p>Please verify your account by clicking <a href="{url}">here</a></p>'
        await self._send(to_email, subject, html)

    async def send_password_reset(self, to_email: str, token: str) -> None:
        """Send password reset email containing a token link."""
        subject = "Reset your password"
        s = Settings()
        url = f"{s.frontend_url}/reset-password?token={token}"
        html = f'<p>Reset your password <a href="{url}">here</a></p>'
        await self._send(to_email, subject, html)
