"""HTTPS redirect middleware for production environments."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Redirects HTTP requests to HTTPS in production.

    Only applies when environment is 'production' to allow local development.
    """

    def __init__(self, app, environment: str = "development"):
        super().__init__(app)
        self.environment = environment.lower()

    async def dispatch(self, request: Request, call_next):
        # Only redirect in production environment
        if self.environment != "production":
            return await call_next(request)

        # Skip if already HTTPS
        if request.url.scheme == "https":
            return await call_next(request)

        # Check for proxy headers (e.g., behind load balancer)
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        if forwarded_proto.lower() == "https":
            return await call_next(request)

        # Redirect to HTTPS
        url = request.url.replace(scheme="https")
        return RedirectResponse(url=url, status_code=307)  # Temporary redirect
