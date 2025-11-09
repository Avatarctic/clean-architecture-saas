"""Caching decorator for feature flag repository."""

import logging
from typing import Optional

from src.app.ports.cache import CacheClient


class CachingFeatureFlagRepository:
    """Cache-aside wrapper for feature flag repository.

    Keys:
      feature:{tenant_id}:{key}
      feature:id:{id}
      feature:list:{tenant_id}
    """

    def __init__(self, inner, cache: Optional[CacheClient], ttl: int = 60):
        self.inner = inner
        self.cache = cache
        self.ttl = ttl

    async def create(
        self,
        tenant_id,
        key,
        name,
        description,
        is_enabled,
        type: str = "boolean",
        enabled_value: dict | None = None,
        default_value: dict | None = None,
        rules: list | None = None,
        rollout: dict | None = None,
    ):
        result = await self.inner.create(
            tenant_id,
            key,
            name,
            description,
            is_enabled,
            type=type,
            enabled_value=enabled_value,
            default_value=default_value,
            rules=rules,
            rollout=rollout,
        )
        # Invalidate any cache entries for this tenant/key
        if self.cache is not None:
            try:
                await self.cache.delete(f"feature:{tenant_id}:{key}")
                # invalidate listing caches for tenant-level lists
                try:
                    await self.cache.delete(f"feature:list:{tenant_id}")
                except Exception as e:
                    # non-fatal: log the inner failure for diagnostics
                    logging.getLogger(__name__).debug(
                        "feature_list_delete_inner_failed",
                        extra={"tenant_id": tenant_id, "error": str(e)},
                    )
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "feature_cache_delete_failed_on_create",
                    extra={"tenant_id": tenant_id, "key": key, "error": str(e)},
                )
        return result

    async def get_by_key(self, tenant_id, key):
        if self.cache is not None:
            try:
                val = await self.cache.get(f"feature:{tenant_id}:{key}")
                # Only return cached values that are full serialized records (dict).
                # Some code paths cache a minimal boolean string for fast evaluation;
                # returning that directly here would make the API return a raw string
                # instead of the expected JSON object. If cached value is a dict,
                # return it; otherwise fall through to fetch full record from inner repo.
                if val is not None and isinstance(val, dict):
                    return val
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "feature_cache_get_failed",
                    extra={"tenant_id": tenant_id, "key": key, "error": str(e)},
                )
        return await self.inner.get_by_key(tenant_id, key)

    async def get_by_id(self, id):
        return await self.inner.get_by_id(id)

    async def update(self, id, **fields):
        result = await self.inner.update(id, **fields)
        # Invalidate relevant cache entries conservatively
        if self.cache is not None:
            try:
                # nothing fancy: in real code we'd map id->tenant/key; conservatively delete id key + potential tenant/global keys
                await self.cache.delete(f"feature:id:{id}")
                # conservatively invalidate tenant listing caches (unknown tenant_id here)
                try:
                    # attempt to read the updated feature to get tenant_id
                    feat = await self.inner.get_by_id(id)
                    if feat is not None:
                        await self.cache.delete(
                            f"feature:{feat.get('tenant_id')}:{feat.get('key')}"
                        )
                        try:
                            await self.cache.delete(f"feature:list:{feat.get('tenant_id')}")
                        except Exception as e:
                            logging.getLogger(__name__).debug(
                                "feature_list_delete_failed_on_update",
                                extra={
                                    "tenant_id": feat.get("tenant_id"),
                                    "error": str(e),
                                },
                            )
                except Exception:
                    # best-effort: ignore failures when attempting to determine tenant for cache invalidation
                    pass
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "feature_cache_delete_failed_on_update",
                    extra={"feature_id": id, "error": str(e)},
                )
        return result

    async def delete(self, id):
        # attempt to read existing feature to identify tenant/key for cache cleanup
        try:
            existing = await self.inner.get_by_id(id)
        except Exception as e:
            # best-effort: if reading existing feature fails, continue and log
            logging.getLogger(__name__).debug(
                "feature_get_before_delete_failed",
                extra={"feature_id": id, "error": str(e)},
            )
            existing = None
        await self.inner.delete(id)
        if self.cache is not None:
            try:
                await self.cache.delete(f"feature:id:{id}")
                if existing is not None:
                    await self.cache.delete(
                        f"feature:{existing.get('tenant_id')}:{existing.get('key')}"
                    )
                    try:
                        await self.cache.delete(f"feature:list:{existing.get('tenant_id')}")
                    except Exception as e:
                        logging.getLogger(__name__).debug(
                            "feature_list_delete_failed",
                            extra={
                                "tenant_id": existing.get("tenant_id"),
                                "error": str(e),
                            },
                        )
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "feature_cache_delete_failed_on_delete",
                    extra={"feature_id": id, "error": str(e)},
                )

    async def list(self, tenant_id, limit, offset):
        return await self.inner.list(tenant_id, limit, offset)

    async def list_all(self, tenant_id=None, limit: int = 50, offset: int = 0):
        """Compatibility alias: prefer inner.list_all if present, otherwise delegate to list().

        Also cache a tenant-scoped listing under feature:list:{tenant_id} when available.
        """
        key = f"feature:list:{tenant_id}"
        if self.cache is not None:
            try:
                v = await self.cache.get(key)
                if v is not None:
                    return v
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "feature_list_cache_get_failed",
                    extra={"tenant_id": tenant_id, "error": str(e)},
                )

        # Fetch from inner repository
        rows = await self.inner.list(tenant_id, limit, offset)

        if rows is not None and self.cache is not None:
            try:
                await self.cache.set(key, rows, ex=self.ttl)
            except Exception as e:
                logging.getLogger(__name__).debug(
                    "feature_list_cache_set_failed",
                    extra={"tenant_id": tenant_id, "error": str(e)},
                )
        return rows
