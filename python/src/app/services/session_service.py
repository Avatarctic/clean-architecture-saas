"""Service layer for session and token management operations."""

from typing import Any, Dict, List

from ..logging_config import get_logger

logger = get_logger(__name__)


class SessionService:
    """Encapsulates session and token management business logic."""

    def __init__(self, tokens_repo: Any, cache: Any = None):
        self.tokens_repo = tokens_repo
        self.cache = cache

    async def revoke_user_session(self, token_hash: str) -> bool:
        """
        Revoke a specific refresh token by token hash.

        Returns:
            True if revoked successfully, False otherwise
        """
        try:
            await self.tokens_repo.revoke_refresh_token(token_hash)

            # Also remove from cache if available
            if self.cache:
                try:
                    await self.cache.delete(f"session:{token_hash}")
                except Exception as e:
                    logger.debug(
                        "cache_delete_failed", extra={"token_hash": token_hash, "error": str(e)}
                    )

            return True
        except Exception as e:
            logger.exception(
                "revoke_token_failed", extra={"token_hash": token_hash, "error": str(e)}
            )
            return False

    async def revoke_all_user_sessions(self, user_id: int) -> Dict[str, Any]:
        """
        Revoke all refresh tokens for a user.

        Returns:
            Dict with 'revoked_count' and 'failed_count'
        """
        revoked_count = 0
        failed_count = 0

        try:
            tokens = await self.tokens_repo.list_refresh_tokens_by_user(user_id)

            for token_data in tokens:
                token_hash = token_data.get("token_hash")
                if token_hash:
                    try:
                        await self.tokens_repo.revoke_refresh_token(token_hash)

                        # Also remove from cache if available
                        if self.cache:
                            try:
                                await self.cache.delete(f"session:{token_hash}")
                            except Exception:
                                pass  # Cache deletion is not critical

                        revoked_count += 1
                    except Exception as e:
                        logger.debug(
                            "revoke_token_in_loop_failed",
                            extra={"token_hash": token_hash, "error": str(e)},
                        )
                        failed_count += 1
        except Exception as e:
            logger.exception(
                "revoke_all_tokens_failed", extra={"user_id": user_id, "error": str(e)}
            )
            raise ValueError(f"Failed to revoke tokens for user {user_id}")

        return {
            "revoked_count": revoked_count,
            "failed_count": failed_count,
            "total_count": revoked_count + failed_count,
        }

    async def list_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """List all sessions (refresh tokens) for a user."""
        result: List[Dict[str, Any]] = await self.tokens_repo.list_sessions_by_user(user_id)
        return result
