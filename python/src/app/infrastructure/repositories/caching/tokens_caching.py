"""Caching decorator for tokens repository."""

from typing import Any


class CachingTokensRepository:
    """Composite repository combining database token operations with session cache.

    This follows the decorator pattern used by other caching repositories, but also
    integrates session cache operations for access tokens stored in Redis.

    Database operations (refresh tokens, blacklist): Delegated to inner repository
    Cache operations (access tokens, session lists): Handled by session_cache
    """

    def __init__(self, inner: Any, session_cache: Any):
        """Initialize with database token repository and session cache repository.

        Args:
            inner: SqlAlchemyTokensRepository for database operations
            session_cache: SessionCacheRepository for cache operations
        """
        self.inner = inner
        self.session_cache = session_cache

    # Database operations - delegate to inner repository
    async def create_refresh_token(self, user_id: int, token_hash: str) -> None:
        await self.inner.create_refresh_token(user_id, token_hash)

    async def list_refresh_tokens_by_user(self, user_id: int):
        return await self.inner.list_refresh_tokens_by_user(user_id)

    async def revoke_refresh_token(self, token_hash: str) -> None:
        await self.inner.revoke_refresh_token(token_hash)

    async def purge_refresh_tokens(self, keep_revoked_for_seconds: int | None = None) -> int:
        result: int = await self.inner.purge_refresh_tokens(keep_revoked_for_seconds)
        return result

    async def is_token_blacklisted(self, token: str) -> bool:
        result: bool = await self.inner.is_token_blacklisted(token)
        return result

    async def blacklist_token(self, user_id: int, token: str, expires_at) -> None:
        await self.inner.blacklist_token(user_id, token, expires_at)

    async def find_by_token_hash(self, token_hash: str):
        return await self.inner.find_by_token_hash(token_hash)

    async def add_session(
        self, user_id: int, access_hash: str, token: str, ex: int | None = None
    ) -> None:
        """Store an access token in cache."""
        await self.session_cache.add_session(user_id, access_hash, token, ex)

    async def get_session(self, session_id: str):
        """Retrieve an access token from cache."""
        return await self.session_cache.get_session(session_id)

    async def list_sessions_by_user(self, user_id: int):
        """List all active sessions for a user."""
        return await self.session_cache.list_user_sessions(user_id)

    async def revoke_session(self, session_id: str) -> None:
        """Revoke a single session."""
        await self.session_cache.revoke_session(session_id)

    async def revoke_all_user_sessions(self, user_id: int) -> int:
        """Revoke all sessions for a user."""
        result: int = await self.session_cache.revoke_all_user_sessions(user_id)
        return result

    def __getattr__(self, name):
        """Delegate any other methods to inner repository."""
        return getattr(self.inner, name)
