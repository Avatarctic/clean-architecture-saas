import asyncio
import importlib
import json
import time
from types import ModuleType
from typing import Any, Optional

# redis.asyncio may not be installed in test environments; keep a typed optional reference
_redis_asyncio: ModuleType | None
_redis_import_error: Exception | None = None
# Import redis.asyncio lazily and defensively: some test environments may not have
# redis installed. Catch all import-time errors and mark the adapter as unavailable;
# the concrete client will raise a RuntimeError with the original error when attempted
# to be constructed.
try:
    _redis_asyncio = importlib.import_module("redis.asyncio")  # type: ignore[attr-defined]
except Exception as e:  # noqa: BLE001 - be broad intentionally for imports
    _redis_asyncio = None
    _redis_import_error = e


def _record_cache_operation(
    operation: str,
    cache_type: str,
    duration: float | None = None,
    hit: bool | None = None,
    key: str | None = None,
):
    """Record cache metrics (lazy import to avoid circular dependency)."""
    try:
        from ...metrics import CACHE_HITS, CACHE_MISSES, CACHE_OPERATION_DURATION, CACHE_OPERATIONS

        metrics = CACHE_OPERATIONS
        if metrics is not None:
            metrics.labels(operation=operation, cache_type=cache_type).inc()

        duration_metric = CACHE_OPERATION_DURATION
        if duration is not None and duration_metric is not None:
            duration_metric.labels(operation=operation, cache_type=cache_type).observe(duration)

        if hit is not None and key is not None:
            # Extract key pattern (e.g., "tenant:id:*", "user:email:*")
            key_pattern = ":".join(key.split(":")[:2]) + ":*" if ":" in key else "other"
            if hit:
                hits_metric = CACHE_HITS
                if hits_metric is not None:
                    hits_metric.labels(cache_type=cache_type, key_pattern=key_pattern).inc()
            else:
                misses_metric = CACHE_MISSES
                if misses_metric is not None:
                    misses_metric.labels(cache_type=cache_type, key_pattern=key_pattern).inc()
    except Exception:
        # Silently ignore metrics errors to not break cache operations
        pass


class InMemoryCache:
    def __init__(self):
        # store: key -> (value: Any, expire_at: Optional[float])
        self.store: dict[str, tuple[Any, Optional[float]]] = {}
        self.lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        start = time.time()
        async with self.lock:
            entry = self.store.get(key)
            if not entry:
                _record_cache_operation("get", "in_memory", time.time() - start, hit=False, key=key)
                return None
            value, expire_at = entry
            if expire_at is not None and time.time() >= expire_at:
                # expired; remove and return None
                try:
                    del self.store[key]
                except KeyError:
                    pass
                _record_cache_operation("get", "in_memory", time.time() - start, hit=False, key=key)
                return None
            _record_cache_operation("get", "in_memory", time.time() - start, hit=True, key=key)
            return value

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        start = time.time()
        expire_at = None
        if ex is not None:
            expire_at = time.time() + int(ex)
        async with self.lock:
            self.store[key] = (value, expire_at)
        _record_cache_operation("set", "in_memory", time.time() - start)

    async def incr(self, key: str) -> int:
        start = time.time()
        async with self.lock:
            entry = self.store.get(key)
            if not entry:
                v = 1
                self.store[key] = (str(v), None)
                return v
            value, expire_at = entry
            # if expired, reset
            if expire_at is not None and time.time() >= expire_at:
                v = 1
                self.store[key] = (str(v), None)
                return v
            try:
                v = int(value) + 1
            except Exception as e:
                try:
                    import logging

                    logging.getLogger(__name__).debug(
                        "in_memory_incr_parse_failed",
                        extra={"key": key, "value": value, "error": str(e)},
                    )
                except Exception:
                    # swallow logging failures
                    pass
                # fallback to starting at 1
                v = 1
            self.store[key] = (str(v), expire_at)
            return v
        _record_cache_operation("incr", "in_memory", time.time() - start)

    async def expire(self, key: str, seconds: int) -> None:
        start = time.time()
        async with self.lock:
            entry = self.store.get(key)
            if not entry:
                return
            value, _ = entry
            self.store[key] = (value, time.time() + int(seconds))
        _record_cache_operation("expire", "in_memory", time.time() - start)

    async def delete(self, key: str) -> None:
        start = time.time()
        async with self.lock:
            if key in self.store:
                del self.store[key]
        _record_cache_operation("delete", "in_memory", time.time() - start)


class AioredisClient:
    def __init__(self, url: str):
        if _redis_asyncio is None:
            msg = "redis.asyncio not available"
            if _redis_import_error is not None:
                msg += f": {type(_redis_import_error).__name__}: {_redis_import_error}"
            raise RuntimeError(msg)
        # construct a redis client from the imported redis.asyncio module
        self.client = _redis_asyncio.from_url(url, decode_responses=False)  # type: ignore[attr-defined]

    async def get(self, key: str) -> Optional[Any]:
        start = time.time()
        v = await self.client.get(key)
        hit = v is not None
        _record_cache_operation("get", "redis", time.time() - start, hit=hit, key=key)
        if not v:
            return None
        text = v.decode()
        try:
            result: Any = json.loads(text)
            return result
        except json.JSONDecodeError as e:
            try:
                import logging

                logging.getLogger(__name__).debug(
                    "redis_json_decode_failed",
                    extra={"key": key, "text": text, "error": str(e)},
                )
            except Exception:
                # swallow logging failures
                pass
            # fallback to raw decoded string
            return text

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        start = time.time()
        # store JSON-serializable objects
        try:
            text = json.dumps(value)
        except Exception:
            text = str(value)
        await self.client.set(key, text, ex=ex)
        _record_cache_operation("set", "redis", time.time() - start)

    async def incr(self, key: str) -> int:
        start = time.time()
        result: int = await self.client.incr(key)
        _record_cache_operation("incr", "redis", time.time() - start)
        return result

    async def expire(self, key: str, seconds: int) -> None:
        start = time.time()
        await self.client.expire(key, seconds)
        _record_cache_operation("expire", "redis", time.time() - start)

    async def delete(self, key: str) -> None:
        start = time.time()
        await self.client.delete(key)
        _record_cache_operation("delete", "redis", time.time() - start)
