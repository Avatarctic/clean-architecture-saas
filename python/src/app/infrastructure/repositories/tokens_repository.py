from typing import Any, Dict, List

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import models


class SqlAlchemyTokensRepository:
    """Handles refresh tokens, blacklisted tokens and session cache helpers."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self._cache = None

    async def create_refresh_token(self, user_id: int, token_hash: str) -> None:
        # persist an expires_at so tokens can expire server-side
        from datetime import datetime, timedelta

        from src.app.config import settings

        ttl = settings.refresh_token_ttl_seconds
        expires_at = None
        if ttl is not None:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        m = models.RefreshTokenModel(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db_session.add(m)
        await self.db_session.flush()
        try:
            await self.db_session.commit()
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(
                "refresh_token_create_commit_failed", extra={"error": str(e)}
            )
            raise  # Re-raise to prevent silent failure

    async def list_refresh_tokens_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        q = await self.db_session.execute(
            select(models.RefreshTokenModel).where(models.RefreshTokenModel.user_id == user_id)
        )
        rows = q.scalars().all()
        return [
            {
                "token_hash": r.token_hash,
                "revoked": bool(r.revoked),
                "created_at": r.created_at,
            }
            for r in rows
        ]

    async def revoke_refresh_token(self, token_hash: str) -> None:
        await self.db_session.execute(
            update(models.RefreshTokenModel)
            .where(models.RefreshTokenModel.token_hash == token_hash)
            .values(revoked=True)
        )
        await self.db_session.flush()

    async def purge_refresh_tokens(self, keep_revoked_for_seconds: int | None = None) -> int:
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        # predicate for revoked tokens: either all revoked, or revoked and older than cutoff
        if keep_revoked_for_seconds is None:
            revoked_pred = models.RefreshTokenModel.revoked  # type: ignore[assignment]
        else:
            cutoff = now - timedelta(seconds=keep_revoked_for_seconds)
            revoked_pred = (models.RefreshTokenModel.revoked) & (  # type: ignore[assignment]
                models.RefreshTokenModel.created_at < cutoff
            )

        del_stmt = delete(models.RefreshTokenModel).where(
            (
                (models.RefreshTokenModel.expires_at != None)  # noqa: E711
                & (models.RefreshTokenModel.expires_at < now)
            )
            | revoked_pred
        )
        res = await self.db_session.execute(del_stmt)
        await self.db_session.flush()
        try:
            await self.db_session.commit()
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(
                "purge_expired_tokens_commit_failed", extra={"error": str(e)}
            )
            raise  # Re-raise to prevent silent failure
        return int(res.rowcount or 0)

    async def is_token_blacklisted(self, token: str) -> bool:
        q = await self.db_session.execute(
            select(models.BlacklistedTokenModel).where(models.BlacklistedTokenModel.token == token)
        )
        r = q.scalars().first()
        if not r:
            return False
        if r.expires_at is not None:
            from datetime import datetime

            if r.expires_at < datetime.utcnow():
                return False
        return True

    async def blacklist_token(self, user_id: int | None, token: str, expires_at) -> None:
        m = models.BlacklistedTokenModel(
            user_id=user_id, token=token, expires_at=expires_at, reason="logout"
        )
        self.db_session.add(m)
        await self.db_session.flush()
        try:
            await self.db_session.commit()
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(
                "blacklist_token_commit_failed", extra={"error": str(e)}
            )
            raise  # Re-raise to prevent silent failure

    # Session cache helpers (store per-user session lists and session entries in cache)
    async def add_session_cache(
        self, user_id: int, access_hash: str, token: str, ex: int | None = None
    ) -> None:
        try:
            if self._cache is None:
                from src.app.deps import get_cache_client

                self._cache = get_cache_client()
            assert self._cache is not None  # type narrowing
            await self._cache.set(f"session:{access_hash}", token, ex=ex)
            key = f"user_sessions:{user_id}"
            lst = await self._cache.get(key) or []
            if access_hash not in lst:
                lst.append(access_hash)
                ttl = ex + 3600 if ex is not None else None
                await self._cache.set(key, lst, ex=ttl)
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(
                "add_session_cache_failed", extra={"error": str(e)}
            )

    async def list_sessions_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        try:
            if self._cache is None:
                from src.app.deps import get_cache_client

                self._cache = get_cache_client()
            assert self._cache is not None  # type narrowing
            key = f"user_sessions:{user_id}"
            lst = await self._cache.get(key) or []
            sessions = []
            for h in list(lst):
                token = await self._cache.get(f"session:{h}")
                if not token:
                    lst = [x for x in lst if x != h]
                    continue
                sessions.append({"session_id": h, "token": token})
            try:
                await self._cache.set(key, lst)
            except Exception as e:
                # best-effort to persist cleaned list; log if it fails
                import logging

                logging.getLogger(__name__).exception(
                    "user_sessions_set_failed", extra={"error": str(e)}
                )
            return sessions
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(
                "list_sessions_by_user_failed", extra={"error": str(e)}
            )
            return []

    async def revoke_session(self, session_id: str) -> None:
        try:
            if self._cache is None:
                from src.app.deps import get_cache_client

                self._cache = get_cache_client()
            assert self._cache is not None  # type narrowing
            # remove session entry and remove from user_sessions list
            await self._cache.get(f"session:{session_id}")
            try:
                await self._cache.delete(f"session:{session_id}")
            except Exception as e:
                import logging

                logging.getLogger(__name__).exception(
                    "cache_delete_session_failed", extra={"error": str(e)}
                )
            # best-effort: find user_sessions lists and remove session_id
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception("revoke_session_failed", extra={"error": str(e)})

    async def find_by_token_hash(self, token_hash: str):
        q = await self.db_session.execute(
            select(models.RefreshTokenModel).where(
                models.RefreshTokenModel.token_hash == token_hash
            )
        )
        return q.scalars().first()
