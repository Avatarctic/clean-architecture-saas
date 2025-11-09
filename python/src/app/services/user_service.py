from datetime import datetime, timezone
from typing import Optional

# CRITICAL: Set up bcrypt shim BEFORE importing passlib
# Passlib's bcrypt handler tries to read bcrypt.__about__.__version__ during import
try:
    import bcrypt as _bcrypt  # isort: skip
    from types import SimpleNamespace  # isort: skip

    if not hasattr(_bcrypt, "__about__"):
        _bcrypt.__about__ = SimpleNamespace(__version__="4.0.1")  # type: ignore[attr-defined]
    elif not hasattr(_bcrypt.__about__, "__version__"):
        _bcrypt.__about__.__version__ = "4.0.1"  # type: ignore[attr-defined]
except ImportError:
    pass  # bcrypt not installed

from passlib.context import CryptContext  # isort: skip

from ..domain.user import User
from ..logging_config import get_logger
from ..ports.repositories import EmailTokenRepository, UserRepository
from ..services.email_token_service import EmailTokenService
from ..utils.password import validate_password_strength

logger = get_logger(__name__)

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


class UserService:
    def __init__(
        self, user_repo: UserRepository, email_tokens_repo: EmailTokenRepository | None = None
    ):
        self.user_repo = user_repo
        self.email_tokens_repo = email_tokens_repo

    async def create_user(
        self,
        tenant_id: int,
        email: str,
        password: str,
        role: str = "member",
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        # Validate password strength
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            raise ValueError(error_msg)

        hashed = pwd_context.hash(password)
        user = User(
            id=None,
            tenant_id=tenant_id,
            email=email,
            hashed_password=hashed,
            role=role,
            first_name=first_name,
            last_name=last_name,
        )
        created = await self.user_repo.create(user)
        logger.debug(
            "user_created",
            extra={
                "id": getattr(created, "id", None),
                "tenant_id": tenant_id,
                "email": email,
            },
        )
        return created

    async def authenticate_global(self, email: str, password: str) -> Optional[User]:
        """Authenticate user by email globally (across all tenants) for login."""
        user = await self.user_repo.get_by_email_global(email)
        logger.debug(
            "authenticate_global_lookup",
            extra={"email": email, "user_found": bool(user)},
        )
        if user:
            # don't log full hash; show prefix for debugging
            hp = getattr(user, "hashed_password", "")
            logger.debug(
                "authenticate_user_hash",
                extra={"hash_prefix": hp[:8] if hp else None},
            )
        if not user:
            return None
        # Ensure the user account is active before verifying password
        if not user.is_active:
            return None
        if not pwd_context.verify(password, user.hashed_password):
            logger.debug("password_verify_failed", extra={"email": email})
            return None
        return user

    async def set_last_login(self, user_id: int):
        """Set last_login_at on successful login."""
        now = datetime.now(timezone.utc)
        await self.user_repo.update_last_login(user_id, now)

    async def request_password_reset(self, tenant_id: int, email: str, email_sender):
        # find user and create token
        u = await self.user_repo.get_by_email(tenant_id, email)
        if not u:
            return False
        if self.email_tokens_repo is None:
            return False
        token_svc = EmailTokenService(self.email_tokens_repo)
        user_id = int(u.id) if u.id is not None else 0
        token = await token_svc.create_token(user_id, "password_reset")
        await email_sender.send_password_reset(u.email, token)
        return True

    async def reset_password(self, token: str, new_password: str) -> bool:
        # Validate password strength
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(error_msg)

        if self.email_tokens_repo is None:
            return False
        token_svc = EmailTokenService(self.email_tokens_repo)
        data = await token_svc.consume_token(token)
        if not data:
            return False
        user_id = int(data["user_id"])
        hashed = pwd_context.hash(new_password)
        await self.user_repo.set_password(user_id, hashed)
        return True

    async def request_email_change(
        self, tenant_id: int, current_email: str, new_email: str, email_sender
    ) -> bool:
        # find user by current_email
        u = await self.user_repo.get_by_email(tenant_id, current_email)
        if not u:
            return False
        if self.email_tokens_repo is None:
            return False
        token_svc = EmailTokenService(self.email_tokens_repo)
        # store new_email in token payload so confirmation can apply it atomically
        user_id = int(u.id) if u.id is not None else 0
        token = await token_svc.create_token(user_id, "email_update", data={"new_email": new_email})
        await email_sender.send_verification(new_email, token)
        return True

    async def confirm_email_change(self, token: str, new_email: str) -> bool:
        if self.email_tokens_repo is None:
            return False
        token_svc = EmailTokenService(self.email_tokens_repo)
        data = await token_svc.consume_token(token)
        if not data:
            return False
        user_id = int(data["user_id"])
        # prefer new_email from token metadata if present
        meta_new = None
        if isinstance(data.get("data"), dict):
            meta_new = data["data"].get("new_email")
        target_email = meta_new or new_email
        if not target_email:
            return False
        await self.user_repo.set_email(user_id, target_email)
        return True

    async def change_password(
        self,
        user_id: int,
        old_password: str,
        new_password: str,
        tenant_repo=None,
        tokens_repo=None,
        cache=None,
    ) -> bool:
        # verify current password then set new one and invalidate tokens
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return False

        # Validate new password strength
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(error_msg)

        if not pwd_context.verify(old_password, user.hashed_password):
            return False
        hashed = pwd_context.hash(new_password)
        await self.user_repo.set_password(user_id, hashed)
        # revoke refresh tokens stored in DB and delete mirrored cache entries
        if tokens_repo is not None:
            tokens = await tokens_repo.list_refresh_tokens_by_user(user_id)
            for t in tokens:
                th = t.get("token_hash")
                if th:
                    await tokens_repo.revoke_refresh_token(th)
                    # delete any mirrored cache entry keyed by refresh token hash
                    if cache is not None:
                        await cache.delete(f"session:{th}")

        # revoke per-user sessions stored in cache
        if tokens_repo is not None:
            sessions = await tokens_repo.list_sessions_by_user(user_id)
            for s in sessions:
                sid = s.get("session_id")
                if sid:
                    await tokens_repo.revoke_session(sid)
        return True
