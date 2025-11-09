"""Caching decorator for permission repository."""

import logging
from typing import Optional

from src.app.ports.cache import CacheClient


class CachingPermissionRepository:
    """Cache-aside wrapper for permission repository.

    Keys:
      perm:role:{role}
      perm:user:{user_id}
    """

    def __init__(self, inner, cache: Optional[CacheClient], ttl: int = 300):
        self.inner = inner
        self.cache = cache
        self.ttl = int(ttl)

    async def get_role_permissions(self, role):
        key = f"perm:role:{role}"
        if self.cache is not None:
            try:
                v = await self.cache.get(key)
                if v:
                    return v
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "perm_cache_get_failed", extra={"role": role, "error": str(e)}
                )
        perms = await self.inner.get_role_permissions(role)
        if perms is not None and self.cache is not None:
            try:
                await self.cache.set(key, perms, ex=self.ttl)
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "perm_cache_set_failed", extra={"role": role, "error": str(e)}
                )
        return perms

    async def list_user_permissions(self, user_id: int):
        """Cache user permissions to avoid repeated DB queries within cache TTL."""
        key = f"perm:user:{user_id}"
        if self.cache is not None:
            try:
                v = await self.cache.get(key)
                if v is not None:
                    return v
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_perm_cache_get_failed",
                    extra={"user_id": user_id, "error": str(e)},
                )

        perms = await self.inner.list_user_permissions(user_id)

        if perms is not None and self.cache is not None:
            try:
                await self.cache.set(key, perms, ex=self.ttl)
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "user_perm_cache_set_failed",
                    extra={"user_id": user_id, "error": str(e)},
                )

        return perms

    async def add_permission_to_role(self, role, perm):
        res = await self.inner.add_permission_to_role(role, perm)
        if self.cache is not None:
            try:
                await self.cache.delete(f"perm:role:{role}")
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "perm_cache_invalidate_failed",
                    extra={"role": role, "error": str(e)},
                )
        return res

    async def remove_permission_from_role(self, role, perm):
        res = await self.inner.remove_permission_from_role(role, perm)
        if self.cache is not None:
            try:
                await self.cache.delete(f"perm:role:{role}")
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "perm_cache_invalidate_failed",
                    extra={"role": role, "error": str(e)},
                )
        return res

    async def set_role_permissions(self, role, permissions):
        res = await self.inner.set_role_permissions(role, permissions)
        if self.cache is not None:
            try:
                await self.cache.delete(f"perm:role:{role}")
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "perm_cache_invalidate_failed",
                    extra={"role": role, "error": str(e)},
                )
        return res

    def __getattr__(self, name):
        """Delegate any other methods to inner repository."""
        return getattr(self.inner, name)
