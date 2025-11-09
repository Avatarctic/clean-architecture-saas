"""Caching decorator for tenant repository."""

import logging
from typing import Any, Optional

from src.app.domain.tenant import Tenant as DomainTenant
from src.app.ports.cache import CacheClient

from .base import deserialize_tenant


class CachingTenantRepository:
    """Cache-aside wrapper for tenant repository.

    Keys:
      tenant:id:{id}
      tenant:slug:{slug}

    TTL is configurable (seconds). Cache client must implement get/set/delete semantics
    compatible with InMemoryCache/AioredisClient in this project.
    """

    def __init__(self, inner: Any, cache: CacheClient, ttl: int = 300):
        self.inner = inner
        self.cache = cache
        self.ttl = int(ttl)

    async def create(self, tenant: DomainTenant) -> DomainTenant:
        t: DomainTenant = await self.inner.create(tenant)
        try:
            await self.cache.set(
                f"tenant:id:{t.id}",
                {
                    "id": t.id,
                    "name": t.name,
                    "slug": t.slug,
                    "domain": t.domain,
                    "plan": t.plan,
                    "status": t.status,
                    "settings": t.settings,
                    "created_at": (t.created_at.isoformat() if t.created_at is not None else None),
                    "updated_at": (t.updated_at.isoformat() if t.updated_at is not None else None),
                },
                ex=self.ttl,
            )
            if t.slug:
                await self.cache.set(
                    f"tenant:slug:{t.slug}",
                    {
                        "id": t.id,
                        "name": t.name,
                        "slug": t.slug,
                        "domain": t.domain,
                        "plan": t.plan,
                        "status": t.status,
                        "settings": t.settings,
                        "created_at": (
                            t.created_at.isoformat() if t.created_at is not None else None
                        ),
                        "updated_at": (
                            t.updated_at.isoformat() if t.updated_at is not None else None
                        ),
                    },
                    ex=self.ttl,
                )
        except Exception as e:
            logging.getLogger(__name__).exception(
                "tenant_cache_set_failed_on_create", extra={"error": str(e)}
            )
        return t

    async def get_by_id(self, id: int) -> Optional[DomainTenant]:
        try:
            v = await self.cache.get(f"tenant:id:{id}")
            cached = deserialize_tenant(v)
            if cached:
                return cached
        except Exception as e:
            logging.getLogger(__name__).exception(
                "tenant_get_by_id_cache_read_failed", extra={"error": str(e)}
            )
        t: Optional[DomainTenant] = await self.inner.get_by_id(id)
        if t:
            try:
                await self.cache.set(
                    f"tenant:id:{t.id}",
                    {
                        "id": t.id,
                        "name": t.name,
                        "slug": t.slug,
                        "domain": t.domain,
                        "plan": t.plan,
                        "status": t.status,
                        "settings": t.settings,
                        "created_at": (
                            t.created_at.isoformat() if t.created_at is not None else None
                        ),
                        "updated_at": (
                            t.updated_at.isoformat() if t.updated_at is not None else None
                        ),
                    },
                    ex=self.ttl,
                )
                if t.slug:
                    await self.cache.set(
                        f"tenant:slug:{t.slug}",
                        {
                            "id": t.id,
                            "name": t.name,
                            "slug": t.slug,
                            "domain": t.domain,
                            "plan": t.plan,
                            "status": t.status,
                            "settings": t.settings,
                            "created_at": (
                                t.created_at.isoformat() if t.created_at is not None else None
                            ),
                            "updated_at": (
                                t.updated_at.isoformat() if t.updated_at is not None else None
                            ),
                        },
                        ex=self.ttl,
                    )
            except Exception as e:
                logging.getLogger(__name__).exception(
                    "tenant_cache_set_failed", extra={"error": str(e)}
                )
        return t

    async def list_all(self) -> list[DomainTenant]:
        """Return list of tenants. Cache-aside on a single tenant:list:all key.

        Stores a list of tenant dicts (same shape as individual tenant cache entries)
        and deserializes them back to DomainTenant objects on read.
        """
        if self.cache is not None:
            try:
                val = await self.cache.get("tenant:list:all")
                if val:
                    # val expected to be a list of dicts or DomainTenant objects
                    out: list[DomainTenant] = []
                    for item in val:
                        t = deserialize_tenant(item)
                        if t:
                            out.append(t)
                    return out
            except Exception as e:
                # cache read should be best-effort but visible in logs
                logging.getLogger(__name__).exception(
                    "tenant_list_cache_read_failed", extra={"error": str(e)}
                )

        # Fetch from inner repository
        rows: list[DomainTenant] = await self.inner.list_all()
        if rows and self.cache is not None:
            try:
                serial = []
                for t in rows:
                    serial.append(
                        {
                            "id": t.id,
                            "name": t.name,
                            "slug": t.slug,
                            "domain": t.domain,
                            "plan": t.plan,
                            "status": t.status,
                            "settings": t.settings,
                            "created_at": (
                                t.created_at.isoformat() if t.created_at is not None else None
                            ),
                            "updated_at": (
                                t.updated_at.isoformat() if t.updated_at is not None else None
                            ),
                        }
                    )
                await self.cache.set("tenant:list:all", serial, ex=self.ttl)
            except Exception as e:
                logging.getLogger(__name__).exception(
                    "tenant_list_cache_write_failed", extra={"error": str(e)}
                )
        return rows

    async def get_by_slug(self, slug: str) -> Optional[DomainTenant]:
        try:
            v = await self.cache.get(f"tenant:slug:{slug}")
            cached = deserialize_tenant(v)
            if cached:
                return cached
        except Exception as e:
            logging.getLogger(__name__).exception(
                "tenant_get_by_slug_cache_read_failed", extra={"error": str(e)}
            )
        t: Optional[DomainTenant] = await self.inner.get_by_slug(slug)
        if t:
            try:
                await self.cache.set(
                    f"tenant:slug:{t.slug}",
                    {
                        "id": t.id,
                        "name": t.name,
                        "slug": t.slug,
                        "domain": t.domain,
                        "plan": t.plan,
                        "status": t.status,
                        "settings": t.settings,
                        "created_at": (
                            t.created_at.isoformat() if t.created_at is not None else None
                        ),
                        "updated_at": (
                            t.updated_at.isoformat() if t.updated_at is not None else None
                        ),
                    },
                    ex=self.ttl,
                )
                await self.cache.set(
                    f"tenant:id:{t.id}",
                    {
                        "id": t.id,
                        "name": t.name,
                        "slug": t.slug,
                        "domain": t.domain,
                        "plan": t.plan,
                        "status": t.status,
                        "settings": t.settings,
                        "created_at": (
                            t.created_at.isoformat() if t.created_at is not None else None
                        ),
                        "updated_at": (
                            t.updated_at.isoformat() if t.updated_at is not None else None
                        ),
                    },
                    ex=self.ttl,
                )
            except Exception as e:
                logging.getLogger(__name__).exception(
                    "tenant_get_by_slug_cache_write_failed", extra={"error": str(e)}
                )
        return t

    async def update(self, id: int, **fields) -> Optional[DomainTenant]:
        """Update tenant fields and refresh cache."""
        # Update inner repository
        updated: Optional[DomainTenant] = await self.inner.update(id, **fields)

        # overwrite cache with updated data
        try:
            if updated is not None:
                await self.cache.set(
                    f"tenant:id:{updated.id}",
                    {
                        "id": updated.id,
                        "name": updated.name,
                        "slug": updated.slug,
                        "domain": updated.domain,
                        "plan": updated.plan,
                        "status": updated.status,
                        "settings": updated.settings,
                        "created_at": (
                            updated.created_at.isoformat()
                            if updated.created_at is not None
                            else None
                        ),
                        "updated_at": (
                            updated.updated_at.isoformat()
                            if updated.updated_at is not None
                            else None
                        ),
                    },
                    ex=self.ttl,
                )
                if getattr(updated, "slug", None):
                    await self.cache.set(
                        f"tenant:slug:{updated.slug}",
                        {
                            "id": updated.id,
                            "name": updated.name,
                            "slug": updated.slug,
                            "domain": updated.domain,
                            "plan": updated.plan,
                            "status": updated.status,
                            "settings": updated.settings,
                            "created_at": (
                                updated.created_at.isoformat()
                                if updated.created_at is not None
                                else None
                            ),
                            "updated_at": (
                                updated.updated_at.isoformat()
                                if updated.updated_at is not None
                                else None
                            ),
                        },
                        ex=self.ttl,
                    )
        except Exception as e:
            logging.getLogger(__name__).exception(
                "tenant_cache_set_failed", extra={"error": str(e)}
            )
        # invalidate tenant listing cache (best-effort)
        try:
            if self.cache is not None:
                await self.cache.delete("tenant:list:all")
        except Exception as e:
            logging.getLogger(__name__).exception(
                "tenant_list_invalidate_failed", extra={"error": str(e)}
            )
        return updated

    async def delete(self, id: int) -> None:
        # attempt to fetch to delete slug key as well
        try:
            existing = await self.inner.get_by_id(id)
        except Exception as e:
            logging.getLogger(__name__).exception(
                "tenant_get_before_delete_failed", extra={"error": str(e)}
            )
            existing = None
        await self.inner.delete(id)
        # ensure cache is invalidated for the id and slug (best-effort)
        try:
            if self.cache is not None:
                await self.cache.delete(f"tenant:id:{id}")
                if existing and getattr(existing, "slug", None):
                    await self.cache.delete(f"tenant:slug:{existing.slug}")
        except Exception as e:
            logging.getLogger(__name__).exception(
                "tenant_delete_cache_cleanup_failed", extra={"error": str(e)}
            )
        # invalidate tenant listing cache
        try:
            if self.cache is not None:
                await self.cache.delete("tenant:list:all")
        except Exception as e:
            logging.getLogger(__name__).exception(
                "tenant_list_invalidate_failed", extra={"error": str(e)}
            )

    async def update_status(self, id: int, status: str) -> Optional[DomainTenant]:
        """Update only the tenant status and ensure cache is refreshed/invalidated.

        Attempts to call inner.update_status. If not available, falls back to
        calling inner.update if present or reading the current tenant state.
        After the update, overwrite the cache entries for id and slug (if present)
        or delete them on failure.
        """
        updated = None
        try:
            updated = await self.inner.update_status(id, status)
        except Exception as e:
            logging.getLogger(__name__).exception(
                "tenant_update_status_failed", extra={"error": str(e)}
            )
            updated = None

        # refresh cache if we have an updated tenant, otherwise invalidate id key
        try:
            if updated is not None:
                await self.cache.set(
                    f"tenant:id:{updated.id}",
                    {
                        "id": updated.id,
                        "name": updated.name,
                        "slug": updated.slug,
                        "domain": updated.domain,
                        "plan": updated.plan,
                        "status": updated.status,
                        "settings": updated.settings,
                        "created_at": (
                            updated.created_at.isoformat()
                            if updated.created_at is not None
                            else None
                        ),
                        "updated_at": (
                            updated.updated_at.isoformat()
                            if updated.updated_at is not None
                            else None
                        ),
                    },
                    ex=self.ttl,
                )
                if getattr(updated, "slug", None):
                    await self.cache.set(
                        f"tenant:slug:{updated.slug}",
                        {
                            "id": updated.id,
                            "name": updated.name,
                            "slug": updated.slug,
                            "domain": updated.domain,
                            "plan": updated.plan,
                            "status": updated.status,
                            "settings": updated.settings,
                            "created_at": (
                                updated.created_at.isoformat()
                                if updated.created_at is not None
                                else None
                            ),
                            "updated_at": (
                                updated.updated_at.isoformat()
                                if updated.updated_at is not None
                                else None
                            ),
                        },
                        ex=self.ttl,
                    )
            else:
                # best-effort invalidation
                try:
                    if self.cache is not None:
                        await self.cache.delete(f"tenant:id:{id}")
                except Exception as e:
                    logging.getLogger(__name__).exception(
                        "tenant_cache_delete_failed", extra={"error": str(e)}
                    )
        except Exception as e:
            logging.getLogger(__name__).exception(
                "tenant_cache_set_failed", extra={"error": str(e)}
            )
        # invalidate tenant listing cache
        try:
            if self.cache is not None:
                await self.cache.delete("tenant:list:all")
        except Exception as e:
            logging.getLogger(__name__).exception(
                "tenant_list_invalidate_failed", extra={"error": str(e)}
            )
        return updated
