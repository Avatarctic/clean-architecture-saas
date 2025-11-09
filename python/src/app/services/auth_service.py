import datetime
import hashlib
import secrets
from typing import Any, Optional, Union

from jose import jwt

from ..domain.auth import AuthTokens, TokenClaims
from ..domain.user import User

ALGORITHM = "HS256"


class AuthService:
    def __init__(self, jwt_secret: str, access_token_ttl_seconds: int = 900):
        self.jwt_secret = jwt_secret
        self.access_token_ttl_seconds = access_token_ttl_seconds

    def generate_session_id(self) -> str:
        # legacy kept for compatibility; session id concept replaced by token hash
        return secrets.token_urlsafe(32)

    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(48)

    def hash_refresh_token(self, token: str) -> str:
        # produce a deterministic server-side token identifier
        h = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return h

    def get_token_hash(self, token: str) -> str:
        # generic SHA-256 hash for any token (access or refresh)
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_access_token(
        self,
        data: Union[dict, TokenClaims],
        expires_delta: Optional[datetime.timedelta] = None,
    ) -> str:
        if isinstance(data, TokenClaims):
            claims = data
        else:
            claims = TokenClaims.from_payload(data)

        payload = claims.to_payload()

        now = datetime.datetime.now(datetime.timezone.utc)
        if expires_delta is not None:
            expire = now + expires_delta
        elif claims.expires_at is not None:
            expire = claims.expires_at
        else:
            expire = now + datetime.timedelta(seconds=self.access_token_ttl_seconds)

        payload["exp"] = expire
        if claims.issued_at is not None:
            payload.setdefault("iat", int(claims.issued_at.timestamp()))
        else:
            payload.setdefault("iat", int(now.timestamp()))

        encoded: str = jwt.encode(payload, self.jwt_secret, algorithm=ALGORITHM)
        return encoded

    def verify_token(self, token: str) -> TokenClaims:
        # verify signature and expiry; blacklist/session checks are performed
        # by higher-level async code (dependencies) which can await repository calls.
        payload = jwt.decode(token, self.jwt_secret, algorithms=[ALGORITHM])
        return TokenClaims.from_payload(payload)

    async def create_login_tokens(
        self,
        user: User,
        tokens_repo: Any,
        cache: Any,
    ) -> AuthTokens:
        """
        Handle complete login token creation flow:
        - Generate refresh token and store it
        - Create access token
        - Set up session cache entries

        Returns AuthTokens with access_token, refresh_token, and expires_in.
        """
        # Generate and store refresh token
        refresh_token = self.generate_refresh_token()
        token_hash = self.hash_refresh_token(refresh_token)
        await tokens_repo.create_refresh_token(user.id, token_hash)

        # Create access token with tenant context
        tenant_value = getattr(user, "tenant_id", None)
        try:
            tenant_id = int(tenant_value) if tenant_value is not None else None
        except (TypeError, ValueError):
            tenant_id = None

        claims = TokenClaims(subject=str(user.id), tenant_id=tenant_id)
        access_token = self.create_access_token(claims)
        access_hash = self.get_token_hash(access_token)

        # Set up session cache entries
        await cache.set(
            f"session:{access_hash}",
            access_token,
            ex=self.access_token_ttl_seconds,
        )
        await cache.set(
            f"session:{token_hash}",
            access_token,
            ex=self.access_token_ttl_seconds,
        )
        await tokens_repo.add_session_cache(
            user.id, access_hash, access_token, ex=self.access_token_ttl_seconds
        )

        return AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.access_token_ttl_seconds,
        )

    async def create_refresh_access_token(
        self,
        user_id: int,
        refresh_token_hash: str,
        tokens_repo: Any,
        cache: Any,
        user_repo: Any = None,
    ) -> AuthTokens:
        """
        Create a new access token from a refresh token:
        - Look up user's tenant_id (if user_repo provided)
        - Generate new access token with proper tenant context
        - Set up session cache entries

        Returns AuthTokens with access_token and expires_in.
        """
        # Look up user's tenant_id to maintain tenant context across refresh
        tenant_id = None
        if user_repo is not None:
            try:
                user = await user_repo.get_by_id(user_id)
                if user is not None:
                    tenant_value = getattr(user, "tenant_id", None)
                    try:
                        tenant_id = int(tenant_value) if tenant_value is not None else None
                    except (TypeError, ValueError):
                        tenant_id = None
            except Exception as e:
                # Best effort: if lookup fails, continue without tenant_id
                try:
                    from ..logging_config import get_logger

                    get_logger(__name__).debug(
                        "user_tenant_lookup_failed_in_refresh",
                        extra={"user_id": user_id, "error": str(e)},
                    )
                except Exception:
                    pass

        # Create new access token
        claims = TokenClaims(subject=str(user_id), tenant_id=tenant_id)
        access_token = self.create_access_token(claims)
        access_hash = self.get_token_hash(access_token)

        # Set up session cache entries
        await cache.set(
            f"session:{access_hash}",
            access_token,
            ex=self.access_token_ttl_seconds,
        )
        await cache.set(
            f"session:{refresh_token_hash}",
            access_token,
            ex=self.access_token_ttl_seconds,
        )
        await tokens_repo.add_session_cache(
            user_id, access_hash, access_token, ex=self.access_token_ttl_seconds
        )

        return AuthTokens(
            access_token=access_token,
            expires_in=self.access_token_ttl_seconds,
        )


def create_default_auth_service() -> AuthService:
    # create a runtime Settings instance when someone actually requests the service
    from ..config import Settings

    s = Settings()  # type: ignore[call-arg]
    return AuthService(s.jwt_secret, s.access_token_ttl_seconds)
