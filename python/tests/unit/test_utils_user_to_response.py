from types import SimpleNamespace

from pydantic import EmailStr

from src.app.schemas.auth import user_to_response


def test_user_to_response_minimal():
    u = SimpleNamespace(id=1, tenant_id=2, email="u@example.com", role="member")
    r = user_to_response(u)
    assert r.id == 1
    assert r.tenant_id == 2
    assert r.email == EmailStr("u@example.com")
    assert r.role == "member"


def test_user_to_response_full():
    u = SimpleNamespace(
        id=5,
        tenant_id=10,
        email="full@example.com",
        first_name="First",
        last_name="Last",
        role="admin",
        is_active=False,
        email_verified=True,
        audit_enabled=True,
        last_login_at=None,
        created_at=None,
        updated_at=None,
    )
    r = user_to_response(u)
    assert r.first_name == "First"
    assert r.last_name == "Last"
    assert r.is_active is False
    assert r.email_verified is True
    assert r.audit_enabled is True
