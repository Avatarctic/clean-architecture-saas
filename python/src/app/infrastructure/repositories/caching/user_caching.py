"""Caching decorator for user repository."""

import logging
from typing import Optional

from src.app.domain.user import User as DomainUser
from src.app.ports.cache import CacheClient


class CachingUserRepository:
    """Cache-aside wrapper for user repository.

    Keys:
      user:id:{id}
      user:email:{email}
      user:list:tenant:{tenant_id}
    """

    def __init__(self, inner, cache: Optional[CacheClient], ttl: int = 60):
        self.inner = inner
        self.cache = cache
        self.ttl = int(ttl)

    async def create(self, user):
        u = await self.inner.create(user)
        # invalidate tenant user-list cache for this user's tenant
        try:
            if self.cache is not None and getattr(u, "tenant_id", None) is not None:
                await self.cache.delete(f"user:list:tenant:{u.tenant_id}")
        except Exception as e:
            logging.getLogger(__name__).debug(
                "user_list_cache_invalidate_failed_on_create",
                extra={"tenant_id": getattr(u, "tenant_id", None), "error": str(e)},
            )
        return u

    async def get_by_id(self, id: int):
        if self.cache is not None:
            try:
                v = await self.cache.get(f"user:id:{id}")
                if v:
                    return v
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_cache_get_by_id_failed",
                    extra={"user_id": id, "error": str(e)},
                )
        u = await self.inner.get_by_id(id)
        if u and self.cache is not None:
            try:
                await self.cache.set(f"user:id:{id}", u, ex=self.ttl)
                await self.cache.set(f"user:email:{u.email}", u, ex=self.ttl)
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_cache_set_failed", extra={"user_id": id, "error": str(e)}
                )
        return u

    async def get_by_email(self, tenant_id: int, email: str):
        if self.cache is not None:
            try:
                v = await self.cache.get(f"user:email:{email}")
                if v:
                    return v
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_cache_get_by_email_failed",
                    extra={"email": email, "error": str(e)},
                )
        u = await self.inner.get_by_email(tenant_id, email)
        if u and self.cache is not None:
            try:
                await self.cache.set(f"user:email:{email}", u, ex=self.ttl)
                await self.cache.set(f"user:id:{u.id}", u, ex=self.ttl)
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_cache_set_by_email_failed",
                    extra={
                        "email": email,
                        "user_id": getattr(u, "id", None),
                        "error": str(e),
                    },
                )
        return u

    async def get_by_email_global(self, email: str):
        """Find user by email across all tenants (for login). Uses same cache key as get_by_email."""
        if self.cache is not None:
            try:
                v = await self.cache.get(f"user:email:{email}")
                if v:
                    return v
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_cache_get_by_email_global_failed",
                    extra={"email": email, "error": str(e)},
                )
        u = await self.inner.get_by_email_global(email)
        if u and self.cache is not None:
            try:
                await self.cache.set(f"user:email:{email}", u, ex=self.ttl)
                await self.cache.set(f"user:id:{u.id}", u, ex=self.ttl)
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_cache_set_by_email_global_failed",
                    extra={
                        "email": email,
                        "user_id": getattr(u, "id", None),
                        "error": str(e),
                    },
                )
        return u

    async def update(self, id: int, **fields):
        res = await self.inner.update(id, **fields)
        # overwrite cache
        try:
            if self.cache is not None and res is not None:
                await self.cache.set(f"user:id:{res.id}", res, ex=self.ttl)
                await self.cache.set(f"user:email:{res.email}", res, ex=self.ttl)
        except Exception as e:
            logging.getLogger(__name__).debug(
                "user_cache_overwrite_failed",
                extra={"user_id": getattr(res, "id", None), "error": str(e)},
            )
        # invalidate tenant user-list cache
        try:
            if (
                self.cache is not None
                and res is not None
                and getattr(res, "tenant_id", None) is not None
            ):
                await self.cache.delete(f"user:list:tenant:{res.tenant_id}")
        except Exception as e:
            logging.getLogger(__name__).debug(
                "user_list_cache_invalidate_failed_on_update",
                extra={"tenant_id": getattr(res, "tenant_id", None), "error": str(e)},
            )
        return res

    async def delete(self, id: int):
        current = None
        try:
            current = await self.inner.get_by_id(id)
        except Exception as e:
            logging.getLogger(__name__).debug(
                "user_fetch_before_delete_failed",
                extra={"user_id": id, "error": str(e)},
            )
        await self.inner.delete(id)
        try:
            if self.cache is not None:
                await self.cache.delete(f"user:id:{id}")
                if current and getattr(current, "email", None):
                    await self.cache.delete(f"user:email:{current.email}")
        except Exception as e:
            logging.getLogger(__name__).debug(
                "user_cache_delete_failed", extra={"user_id": id, "error": str(e)}
            )
        # invalidate tenant user-list cache for the user's tenant
        try:
            if (
                self.cache is not None
                and current is not None
                and getattr(current, "tenant_id", None) is not None
            ):
                await self.cache.delete(f"user:list:tenant:{current.tenant_id}")
        except Exception as e:
            logging.getLogger(__name__).debug(
                "user_list_cache_invalidate_failed_on_delete",
                extra={
                    "tenant_id": getattr(current, "tenant_id", None),
                    "error": str(e),
                },
            )

    async def list_by_tenant(self, tenant_id: int) -> list[DomainUser]:
        key = f"user:list:tenant:{tenant_id}"
        if self.cache is not None:
            try:
                v = await self.cache.get(key)
                if v:
                    # Cache stores list of User objects
                    return v  # type: ignore[no-any-return]
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_list_cache_get_failed",
                    extra={"tenant_id": tenant_id, "error": str(e)},
                )
        rows: list[DomainUser] = await self.inner.list_by_tenant(tenant_id)
        if rows is not None and self.cache is not None:
            try:
                await self.cache.set(key, rows, ex=self.ttl)
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_list_cache_set_failed",
                    extra={"tenant_id": tenant_id, "error": str(e)},
                )
        return rows

    async def set_password(self, user_id: int, hashed_password: str) -> None:
        """Set user password and invalidate caches."""
        await self.inner.set_password(user_id, hashed_password)
        if self.cache is not None:
            try:
                # Invalidate cached user data since password changed
                user = await self.inner.get_by_id(user_id)
                await self.cache.delete(f"user:id:{user_id}")
                if user and getattr(user, "email", None):
                    await self.cache.delete(f"user:email:{user.email}")
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_cache_invalidate_after_password_failed",
                    extra={"user_id": user_id, "error": str(e)},
                )

    async def update_last_login(self, user_id: int, when) -> None:
        """Update last login time and invalidate caches."""
        await self.inner.update_last_login(user_id, when)
        if self.cache is not None:
            try:
                # Invalidate cached user data since last_login_at changed
                user = await self.inner.get_by_id(user_id)
                await self.cache.delete(f"user:id:{user_id}")
                if user and getattr(user, "email", None):
                    await self.cache.delete(f"user:email:{user.email}")
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_cache_invalidate_after_login_failed",
                    extra={"user_id": user_id, "error": str(e)},
                )

    async def set_email(self, user_id: int, new_email: str) -> None:
        """Set user email and invalidate caches."""
        # Get old email before change
        old_user = None
        try:
            old_user = await self.inner.get_by_id(user_id)
        except Exception as e:
            logging.getLogger(__name__).debug(
                "user_fetch_before_email_change_failed",
                extra={"user_id": user_id, "error": str(e)},
            )

        await self.inner.set_email(user_id, new_email)

        if self.cache is not None:
            try:
                # Invalidate both old and new email caches
                await self.cache.delete(f"user:id:{user_id}")
                if old_user and getattr(old_user, "email", None):
                    await self.cache.delete(f"user:email:{old_user.email}")
                await self.cache.delete(f"user:email:{new_email}")
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_cache_invalidate_after_email_change_failed",
                    extra={"user_id": user_id, "error": str(e)},
                )
