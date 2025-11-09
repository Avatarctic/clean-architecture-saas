"""Unit tests for AuthService."""

import datetime
import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.domain.auth import AuthTokens, TokenClaims
from src.app.domain.user import User
from src.app.services.auth_service import AuthService


@pytest.fixture
def auth_service():
    """Create AuthService instance with test JWT secret."""
    return AuthService(jwt_secret="test_secret_key_123", access_token_ttl_seconds=900)


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    return User(
        id=42,
        tenant_id=1,
        email="test@example.com",
        hashed_password="$pbkdf2$hashed",
        role="user",
        is_active=True,
    )


def test_generate_refresh_token(auth_service):
    """Test that generate_refresh_token creates unique tokens."""
    token1 = auth_service.generate_refresh_token()
    token2 = auth_service.generate_refresh_token()

    assert token1 != token2
    assert len(token1) > 32  # Should be reasonably long
    assert isinstance(token1, str)


def test_hash_refresh_token(auth_service):
    """Test that hash_refresh_token produces consistent SHA256 hashes."""
    token = "test_token_123"
    hash1 = auth_service.hash_refresh_token(token)
    hash2 = auth_service.hash_refresh_token(token)

    # Same token should produce same hash
    assert hash1 == hash2

    # Verify it's a SHA256 hash (64 hex chars)
    assert len(hash1) == 64

    # Verify it matches direct SHA256
    expected = hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert hash1 == expected


def test_get_token_hash(auth_service):
    """Test that get_token_hash produces SHA256 hashes."""
    token = "access_token_xyz"
    hash1 = auth_service.get_token_hash(token)

    assert len(hash1) == 64
    expected = hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert hash1 == expected


def test_create_access_token_from_claims(auth_service):
    """Test creating access token from TokenClaims."""
    claims = TokenClaims(subject="123", tenant_id=1)
    token = auth_service.create_access_token(claims)

    assert isinstance(token, str)
    assert len(token) > 50  # JWT tokens are long

    # Verify token can be decoded
    decoded = auth_service.verify_token(token)
    assert decoded.subject == "123"
    assert decoded.tenant_id == 1


def test_create_access_token_from_dict(auth_service):
    """Test creating access token from dictionary."""
    data = {"sub": "456", "tenant_id": 2}
    token = auth_service.create_access_token(data)

    assert isinstance(token, str)

    # Verify token can be decoded
    decoded = auth_service.verify_token(token)
    assert decoded.subject == "456"
    assert decoded.tenant_id == 2


def test_create_access_token_with_custom_expiry(auth_service):
    """Test creating access token with custom expiration."""
    claims = TokenClaims(subject="789", tenant_id=3)
    custom_delta = datetime.timedelta(seconds=300)  # 5 minutes

    token = auth_service.create_access_token(claims, expires_delta=custom_delta)

    decoded = auth_service.verify_token(token)
    assert decoded.subject == "789"


def test_verify_token_valid(auth_service):
    """Test verifying a valid token."""
    claims = TokenClaims(subject="100", tenant_id=5)
    token = auth_service.create_access_token(claims)

    decoded = auth_service.verify_token(token)
    assert decoded.subject == "100"
    assert decoded.tenant_id == 5
    assert decoded.expires_at is not None


def test_verify_token_expired(auth_service):
    """Test that expired tokens raise an exception."""
    from jose import JWTError

    claims = TokenClaims(subject="200", tenant_id=6)
    # Create token that expired 1 hour ago
    datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    token = auth_service.create_access_token(
        claims, expires_delta=datetime.timedelta(seconds=-3600)
    )

    with pytest.raises(JWTError):
        auth_service.verify_token(token)


def test_verify_token_invalid_signature():
    """Test that tokens with invalid signature are rejected."""
    from jose import JWTError

    service1 = AuthService(jwt_secret="secret1", access_token_ttl_seconds=900)
    service2 = AuthService(jwt_secret="secret2", access_token_ttl_seconds=900)

    claims = TokenClaims(subject="300", tenant_id=7)
    token = service1.create_access_token(claims)

    # Trying to verify with different secret should fail
    with pytest.raises(JWTError):
        service2.verify_token(token)


@pytest.mark.asyncio
async def test_create_login_tokens(auth_service, mock_user):
    """Test complete login token creation flow."""
    mock_tokens_repo = AsyncMock()
    mock_tokens_repo.create_refresh_token = AsyncMock()
    mock_tokens_repo.add_session_cache = AsyncMock()

    mock_cache = AsyncMock()
    mock_cache.set = AsyncMock()

    result = await auth_service.create_login_tokens(mock_user, mock_tokens_repo, mock_cache)

    # Verify result structure
    assert isinstance(result, AuthTokens)
    assert result.access_token is not None
    assert result.refresh_token is not None
    assert result.expires_in == 900

    # Verify refresh token was stored
    mock_tokens_repo.create_refresh_token.assert_called_once()
    call_args = mock_tokens_repo.create_refresh_token.call_args
    assert call_args[0][0] == 42  # user_id

    # Verify cache was updated (2 session entries)
    assert mock_cache.set.call_count == 2

    # Verify session cache was added
    mock_tokens_repo.add_session_cache.assert_called_once()


@pytest.mark.asyncio
async def test_create_login_tokens_preserves_tenant_id(auth_service, mock_user):
    """Test that login tokens include tenant_id from user."""
    mock_tokens_repo = AsyncMock()
    mock_tokens_repo.create_refresh_token = AsyncMock()
    mock_tokens_repo.add_session_cache = AsyncMock()

    mock_cache = AsyncMock()
    mock_cache.set = AsyncMock()

    result = await auth_service.create_login_tokens(mock_user, mock_tokens_repo, mock_cache)

    # Decode access token and verify tenant_id
    decoded = auth_service.verify_token(result.access_token)
    assert decoded.tenant_id == 1
    assert decoded.subject == "42"


@pytest.mark.asyncio
async def test_create_refresh_access_token(auth_service):
    """Test creating new access token from refresh token."""
    mock_user_repo = AsyncMock()
    mock_user = MagicMock()
    mock_user.tenant_id = 10
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

    mock_tokens_repo = AsyncMock()
    mock_tokens_repo.add_session_cache = AsyncMock()

    mock_cache = AsyncMock()
    mock_cache.set = AsyncMock()

    refresh_token_hash = "abc123hash"

    result = await auth_service.create_refresh_access_token(
        user_id=99,
        refresh_token_hash=refresh_token_hash,
        tokens_repo=mock_tokens_repo,
        cache=mock_cache,
        user_repo=mock_user_repo,
    )

    # Verify result structure
    assert isinstance(result, AuthTokens)
    assert result.access_token is not None
    assert result.expires_in == 900

    # Verify new access token has correct claims
    decoded = auth_service.verify_token(result.access_token)
    assert decoded.subject == "99"
    assert decoded.tenant_id == 10

    # Verify user lookup was performed
    mock_user_repo.get_by_id.assert_called_once_with(99)

    # Verify cache was updated
    assert mock_cache.set.call_count == 2


@pytest.mark.asyncio
async def test_create_refresh_access_token_without_user_repo(auth_service):
    """Test refresh token creation without user repository (no tenant_id lookup)."""
    mock_tokens_repo = AsyncMock()
    mock_tokens_repo.add_session_cache = AsyncMock()

    mock_cache = AsyncMock()
    mock_cache.set = AsyncMock()

    refresh_token_hash = "xyz789hash"

    result = await auth_service.create_refresh_access_token(
        user_id=88,
        refresh_token_hash=refresh_token_hash,
        tokens_repo=mock_tokens_repo,
        cache=mock_cache,
        user_repo=None,  # No user repo
    )

    # Should still work, but tenant_id will be None
    decoded = auth_service.verify_token(result.access_token)
    assert decoded.subject == "88"
    assert decoded.tenant_id is None


@pytest.mark.asyncio
async def test_create_refresh_access_token_handles_user_lookup_failure(auth_service):
    """Test that refresh token creation handles user lookup failures gracefully."""
    mock_user_repo = AsyncMock()
    mock_user_repo.get_by_id = AsyncMock(side_effect=Exception("DB error"))

    mock_tokens_repo = AsyncMock()
    mock_tokens_repo.add_session_cache = AsyncMock()

    mock_cache = AsyncMock()
    mock_cache.set = AsyncMock()

    # Should not raise exception, just continue without tenant_id
    result = await auth_service.create_refresh_access_token(
        user_id=77,
        refresh_token_hash="error_hash",
        tokens_repo=mock_tokens_repo,
        cache=mock_cache,
        user_repo=mock_user_repo,
    )

    assert result.access_token is not None
    decoded = auth_service.verify_token(result.access_token)
    assert decoded.subject == "77"
    assert decoded.tenant_id is None  # Failed lookup, no tenant_id


def test_token_contains_iat_claim(auth_service):
    """Test that tokens contain 'iat' (issued at) claim."""
    claims = TokenClaims(subject="111", tenant_id=8)
    token = auth_service.create_access_token(claims)

    # Decode manually to check raw payload
    from jose import jwt

    payload = jwt.decode(token, auth_service.jwt_secret, algorithms=["HS256"])

    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_custom_access_token_ttl():
    """Test creating AuthService with custom TTL."""
    service = AuthService(jwt_secret="test_key", access_token_ttl_seconds=1800)

    assert service.access_token_ttl_seconds == 1800

    claims = TokenClaims(subject="222", tenant_id=9)
    token = service.create_access_token(claims)

    # Token should be valid
    decoded = service.verify_token(token)
    assert decoded.subject == "222"
