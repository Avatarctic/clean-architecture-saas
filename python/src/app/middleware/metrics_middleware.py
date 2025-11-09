import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..metrics import REQUEST_COUNT, REQUEST_LATENCY, TENANT_REQUESTS


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        latency = time.time() - start
        endpoint = request.url.path
        method = request.method

        # Record standard HTTP metrics
        if REQUEST_LATENCY is not None:
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(latency)
        if REQUEST_COUNT is not None:
            REQUEST_COUNT.labels(
                method=method, endpoint=endpoint, http_status=str(response.status_code)
            ).inc()

        # Record tenant-specific metrics if tenant is resolved
        tenant = getattr(request.state, "tenant", None)
        if tenant:
            tenant_id = str(getattr(tenant, "id", "unknown"))
            tenant_slug = str(getattr(tenant, "slug", "unknown"))
            if TENANT_REQUESTS is not None:
                TENANT_REQUESTS.labels(tenant_id=tenant_id, tenant_slug=tenant_slug).inc()

        return response
