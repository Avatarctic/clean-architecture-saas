"""Cache-only repository for email verification/password reset tokens.

Email tokens are stored in Redis with a 1-hour TTL. They are ephemeral by design
and can be regenerated if lost (e.g., user clicks "resend verification email").
"""

from typing import Any, Dict, Optional


class EmailTokenCacheRepository:
    """Manages email verification and password reset tokens in cache."""

    def __init__(self, cache):
        """Initialize with a cache client (Redis or InMemoryCache).

        Args:
            cache: Cache client implementing get/set/delete operations
        """
        self.cache = cache

    async def create_token(
        self, user_id: int, token: str, purpose: str, data: dict | None = None, ttl: int = 3600
    ) -> None:
        """Store an email token in cache with configurable TTL (default 1 hour).

        Args:
            user_id: User ID the token belongs to
            token: The token string (should be cryptographically random)
            purpose: Token purpose (e.g., "password_reset", "email_update")
            data: Optional additional data to store with token
            ttl: Time-to-live in seconds (default 3600 = 1 hour)
        """
        try:
            key = f"emailtoken:{token}"
            payload = {"user_id": user_id, "purpose": purpose}
            if isinstance(data, dict):
                for k, v in data.items():
                    if k in ("user_id", "purpose"):
                        continue
                    payload[k] = v
            # Tokens expire and can be regenerated
            await self.cache.set(key, payload, ex=ttl)
        except Exception as e:
            try:
                from ...logging_config import get_logger

                get_logger(__name__).debug("email_token_cache_set_failed", extra={"error": str(e)})
            except Exception:
                pass

    async def consume_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Retrieve and delete an email token (one-time use).

        Args:
            token: The token string to consume

        Returns:
            Dict with user_id, purpose, and any additional data, or None if not found
        """
        try:
            key = f"emailtoken:{token}"
            val = await self.cache.get(key)
            if not val:
                return None
            # Delete immediately (one-time use)
            await self.cache.delete(key)
            result = {
                "user_id": int(val["user_id"]),
                "purpose": val.get("purpose"),
                "created_at": None,
            }
            # Extract additional data fields
            for k, v in val.items():
                if k not in ("user_id", "purpose"):
                    result.setdefault("data", {})[k] = v
            return result
        except Exception as e:
            try:
                from ...logging_config import get_logger

                get_logger(__name__).debug(
                    "email_token_consume_failed",
                    extra={"token": token, "error": str(e)},
                )
            except Exception:
                pass
            return None
