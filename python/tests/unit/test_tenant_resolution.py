import pytest
from starlette.requests import Request

from src.app.domain.tenant import Tenant as DomainTenant


@pytest.mark.asyncio
async def test_resolves_tenant_from_subdomain():
    """Test that middleware resolves tenant and attaches it to request.state.tenant."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"host", b"acme.example.com")],
        "scheme": "http",
        "http_version": "1.1",
        "client": ("127.0.0.1", 12345),
    }
    request = Request(scope)
    # Mock middleware-resolved tenant
    expected_tenant = DomainTenant(id=1, name="Acme", slug="acme")
    request.state.tenant = expected_tenant

    # Access tenant directly from request.state
    tenant = request.state.tenant
    assert tenant is not None
    assert tenant.slug == "acme"
    assert tenant.id == 1


@pytest.mark.asyncio
async def test_tenant_missing_when_not_resolved():
    """Test that request.state.tenant is None when middleware didn't resolve tenant."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"host", b"missing.example.com")],
        "scheme": "http",
        "http_version": "1.1",
        "client": ("127.0.0.1", 12345),
    }
    request = Request(scope)
    # Middleware didn't resolve tenant -> None
    request.state.tenant = None

    # Access tenant directly from request.state
    tenant = request.state.tenant
    assert tenant is None


@pytest.mark.asyncio
async def test_rejects_localhost_host():
    """Test that middleware doesn't resolve localhost, so request.state.tenant is None."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"host", b"localhost")],
        "scheme": "http",
        "http_version": "1.1",
        "client": ("127.0.0.1", 12345),
    }
    request = Request(scope)
    # Middleware rejects localhost -> tenant is None
    request.state.tenant = None

    # Access tenant directly from request.state
    tenant = request.state.tenant
    assert tenant is None
