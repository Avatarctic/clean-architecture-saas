"""Singleton providers for application-wide services and clients.

This module handles lazy initialization of singleton instances like Settings,
AuthService, cache clients, and email senders.
"""

import sys
from typing import Any

from ..config import Settings
from ..infrastructure.cache.redis_client import InMemoryCache
from ..infrastructure.email.mock import MockEmailSender
from ..infrastructure.email.sendgrid import SendGridEmailSender
from ..ports.email import EmailSender
from ..services.auth_service import AuthService

# Lazy singletons to avoid import-time side-effects
_settings: Settings | None = None
_auth_service: AuthService | None = None


def get_settings() -> Settings:
    """Get or create singleton Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_auth_service() -> AuthService:
    """Get or create singleton AuthService instance."""
    global _auth_service
    if _auth_service is None:
        s = get_settings()
        _auth_service = AuthService(s.jwt_secret, s.access_token_ttl_seconds)
    return _auth_service


def _resolve_app_clients():
    """Dynamic fallback: resolve FastAPI app state at attribute access time.

    This allows tests that reload modules or import deps under different names
    to still read the initialized clients without relying on brittle sys.modules mirrors.
    """
    main_mod = (
        sys.modules.get("src.app.main") or sys.modules.get("app.main") or sys.modules.get("src.app")
    )
    if main_mod:
        app = getattr(main_mod, "app", None)
        if app:
            return getattr(app.state, "cache_client", None), getattr(
                app.state, "email_sender", None
            )
    return None, None


def __getattr__(name: str):
    """Module-level attribute getter for dynamic app client resolution."""
    if name == "_app_cache_client":
        c, _ = _resolve_app_clients()
        return c
    if name == "_app_email_sender":
        _, e = _resolve_app_clients()
        return e
    raise AttributeError(name)


def __dir__():
    """Include dynamic attributes in dir() output."""
    return list(globals().keys()) + ["_app_cache_client", "_app_email_sender"]


def get_email_sender() -> EmailSender:
    """Get email sender: prefer app-initialized sender, fallback to SendGrid or Mock."""
    # prefer app-initialized sender when available (set at startup)
    sender = getattr(sys.modules.get(__name__), "_app_email_sender", None)
    if sender is not None:
        return sender  # type: ignore[no-any-return]

    # choose SendGrid if configured, otherwise mock
    if getattr(get_settings(), "sendgrid_api_key", "") and SendGridEmailSender is not None:
        try:
            return SendGridEmailSender()
        except Exception:
            # fall back to mock if sendgrid client not available at runtime
            return MockEmailSender()
    return MockEmailSender()


def get_cache_client():
    """Get cache client: prefer app-initialized client, fallback to InMemoryCache."""
    # prefer app-initialized cache client when available (set at startup)
    cache = getattr(sys.modules.get(__name__), "_app_cache_client", None)
    if cache is not None:
        return cache

    # for now use in-memory cache; can be overridden to AioredisClient via app startup
    return InMemoryCache()


def get_cache_from_request(request: Any = None):
    """Get cache client from request.app.state with fallback to get_cache_client().

    Eliminates the repetitive pattern of checking request.app.state.cache_client
    and falling back to get_cache_client() throughout the codebase.
    """
    if request is not None:
        cache = getattr(request.app.state, "cache_client", None)
        if cache is not None:
            return cache
    return get_cache_client()
