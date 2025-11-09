# CRITICAL: Set up bcrypt shim BEFORE any passlib imports
# This test imports passlib locally, so we need the shim here
try:
    import bcrypt as _bcrypt  # isort: skip
    from types import SimpleNamespace  # isort: skip

    if not hasattr(_bcrypt, "__about__"):
        _bcrypt.__about__ = SimpleNamespace(__version__="4.0.1")
    elif not hasattr(_bcrypt.__about__, "__version__"):
        _bcrypt.__about__.__version__ = "4.0.1"
except ImportError:
    pass

from unittest.mock import AsyncMock

import pytest

from src.app.domain.user import User
from src.app.services.user_service import UserService


@pytest.mark.asyncio
async def test_create_and_authenticate_user():
    mock_repo = AsyncMock()
    # Use pbkdf2_sha256 instead of bcrypt to avoid bcrypt 4.x compatibility issues in tests
    # The UserService uses CryptContext with both schemes, so this tests the same logic
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    # Use a password that meets the new 12+ character security requirement with complexity
    secure_password = "SecurePass123!"
    hashed = pwd_context.hash(secure_password)
    # mock create to return a user with an id
    mock_repo.create.return_value = User(
        id=1, tenant_id=1, email="a@example.com", hashed_password=hashed
    )
    # mock get_by_email_global to return that user (authenticate_global uses global lookup)
    mock_repo.get_by_email_global.return_value = User(
        id=1, tenant_id=1, email="a@example.com", hashed_password=hashed
    )

    svc = UserService(mock_repo)
    user = await svc.create_user(1, "a@example.com", secure_password)
    assert user.id == 1

    # rely on correct bcrypt hash so pwd_context.verify in service passes
    auth = await svc.authenticate_global("a@example.com", secure_password)
    assert auth is not None
    assert auth.email == "a@example.com"
