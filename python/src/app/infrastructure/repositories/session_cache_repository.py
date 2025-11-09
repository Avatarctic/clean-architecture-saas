"""Session cache repository for managing access tokens in Redis/cache.

This repository handles session cache operations (access tokens, user session lists)
independently from database operations (refresh tokens, blacklist).
"""

import logging
from typing import Any, Dict, List, Optional


class SessionCacheRepository:
    """Repository for session cache operations (access tokens stored in Redis/cache)."""

    def __init__(self, cache: Any):
        """Initialize with a cache client (Redis or InMemoryCache).

        Args:
            cache: Cache client implementing get/set/delete methods
        """
        self.cache = cache
        self.logger = logging.getLogger(__name__)

    async def add_session(
        self, user_id: int, access_hash: str, token: str, ex: Optional[int] = None
    ) -> None:
        """Store an access token in cache and add to user's session list.

        Args:
            user_id: User ID owning this session
            access_hash: Hash of the access token (used as session ID)
            token: The actual access token JWT
            ex: TTL in seconds (optional)
        """
        try:
            # Store the token itself
            await self.cache.set(f"session:{access_hash}", token, ex=ex)

            # Add to user's session list
            key = f"user_sessions:{user_id}"
            lst = (await self.cache.get(key)) or []
            if access_hash not in lst:
                lst.append(access_hash)
                # Session list TTL should be slightly longer than individual tokens
                ttl = (ex + 3600) if ex is not None else None
                await self.cache.set(key, lst, ex=ttl)

        except Exception as e:
            self.logger.exception("add_session_cache_failed", extra={"error": str(e)})

    async def get_session(self, session_id: str) -> Optional[str]:
        """Retrieve an access token from cache.

        Args:
            session_id: Hash of the access token

        Returns:
            Access token JWT or None if not found/expired
        """
        try:
            result: Optional[str] = await self.cache.get(f"session:{session_id}")
            return result
        except Exception as e:
            self.logger.debug(
                "get_session_failed", extra={"session_id": session_id, "error": str(e)}
            )
            return None

    async def list_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """List all active sessions for a user.

        Args:
            user_id: User ID

        Returns:
            List of dicts with session_id and token keys
        """
        try:
            key = f"user_sessions:{user_id}"
            lst = (await self.cache.get(key)) or []
            sessions = []

            # Clean up stale entries while listing
            valid_hashes = []
            for h in list(lst):
                token = await self.cache.get(f"session:{h}")
                if token:
                    sessions.append({"session_id": h, "token": token})
                    valid_hashes.append(h)

            # Update list to remove stale entries
            if len(valid_hashes) != len(lst):
                try:
                    await self.cache.set(key, valid_hashes)
                except Exception as e:
                    self.logger.debug(
                        "user_sessions_cleanup_failed",
                        extra={"user_id": user_id, "error": str(e)},
                    )

            return sessions

        except Exception as e:
            self.logger.exception("list_sessions_by_user_failed", extra={"error": str(e)})
            return []

    async def revoke_session(self, session_id: str) -> None:
        """Revoke a single session by deleting it from cache.

        Args:
            session_id: Hash of the access token to revoke
        """
        try:
            # Delete the session token
            await self.cache.delete(f"session:{session_id}")
        except Exception as e:
            self.logger.exception("revoke_session_failed", extra={"error": str(e)})

    async def revoke_all_user_sessions(self, user_id: int) -> int:
        """Revoke all sessions for a user.

        Args:
            user_id: User ID

        Returns:
            Number of sessions revoked
        """
        try:
            sessions = await self.list_user_sessions(user_id)
            count = 0

            for session in sessions:
                session_id = session.get("session_id")
                if session_id:
                    await self.revoke_session(session_id)
                    count += 1

            # Clear the user's session list
            await self.cache.delete(f"user_sessions:{user_id}")

            return count

        except Exception as e:
            self.logger.exception("revoke_all_user_sessions_failed", extra={"error": str(e)})
            return 0
