from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from ..deps import (
    get_audit_repo,
    get_auth_service,
    get_cache_from_request,
    get_db,
    get_email_sender,
    get_email_tokens_repo,
    get_tenant_repo,
    get_tokens_repo,
    get_user_repo,
    get_user_service,
    require_rate_limit,
)
from ..domain.audit import AuditAction, AuditResource, log_audit_event
from ..logging_config import get_logger
from ..metrics import AUTH_ATTEMPTS, TOKEN_OPERATIONS
from ..schemas.auth import (
    RefreshRequest,
    RefreshResponse,
    TokenRequest,
    TokenResponse,
)
from ..services.auth_service import AuthService
from ..services.email_token_service import EmailTokenService
from ..services.user_service import UserService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    req: TokenRequest,
    user_svc: UserService = Depends(get_user_service),
    tenant_repo=Depends(get_tenant_repo),
    tokens_repo=Depends(get_tokens_repo),
    audit_repo=Depends(get_audit_repo),
    auth_svc: AuthService = Depends(get_auth_service),
    _rl: None = Depends(require_rate_limit),
    request: Request = None,  # type: ignore[assignment]
):
    logger.debug("login endpoint called", extra={"email": req.email})
    user = await user_svc.authenticate_global(req.email, req.password)
    if not user:
        if AUTH_ATTEMPTS is not None:
            AUTH_ATTEMPTS.labels(result="failure", method="login").inc()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if AUTH_ATTEMPTS is not None:
        AUTH_ATTEMPTS.labels(result="success", method="login").inc()

    try:
        user_id = int(user.id) if user.id is not None else 0
        await user_svc.set_last_login(user_id)
    except Exception as e:
        logger.exception(
            "failed_to_set_last_login",
            extra={"user_id": getattr(user, "id", None), "error": str(e)},
        )

    # Create login tokens (delegated to auth service)
    cache = get_cache_from_request(request)

    try:
        issued = await auth_svc.create_login_tokens(user, tokens_repo, cache)
        if TOKEN_OPERATIONS is not None:
            TOKEN_OPERATIONS.labels(operation="generate").inc()
    except Exception as e:
        logger.exception(
            "create_login_tokens_failed",
            extra={"user_id": getattr(user, "id", None), "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="failed to create session")

    # Audit logging
    await log_audit_event(
        audit_repo,
        user,
        AuditAction.LOGIN,
        AuditResource.AUTH,
        {"message": f"user {user.email} logged in"},
        request=request,
    )

    return TokenResponse(
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        token_type="bearer",
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    req: RefreshRequest,
    tenant_repo=Depends(get_tenant_repo),
    tokens_repo=Depends(get_tokens_repo),
    user_repo=Depends(get_user_repo),
    auth_svc: AuthService = Depends(get_auth_service),
    _rl: None = Depends(require_rate_limit),
    request: Request = None,  # type: ignore[assignment]
):
    token_hash = auth_svc.hash_refresh_token(req.refresh_token)
    model = await tokens_repo.find_by_token_hash(token_hash)  # type: ignore[arg-type]
    if not model or getattr(model, "revoked", False):
        if AUTH_ATTEMPTS is not None:
            AUTH_ATTEMPTS.labels(result="failure", method="token_refresh").inc()
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    u = await user_repo.get_by_id(int(model.user_id))
    if u is not None and getattr(u, "is_active", True) is False:
        if AUTH_ATTEMPTS is not None:
            AUTH_ATTEMPTS.labels(result="failure", method="token_refresh").inc()
        raise HTTPException(status_code=401, detail="User inactive")

    if AUTH_ATTEMPTS is not None:
        AUTH_ATTEMPTS.labels(result="success", method="token_refresh").inc()

    # Create new access token (delegated to auth service)
    cache = get_cache_from_request(request)

    issued = await auth_svc.create_refresh_access_token(
        model.user_id, model.token_hash, tokens_repo, cache, user_repo=user_repo
    )
    if TOKEN_OPERATIONS is not None:
        TOKEN_OPERATIONS.labels(operation="refresh").inc()
    return RefreshResponse(access_token=issued.access_token)


@router.post("/logout")
async def logout(
    request: Request,
    tenant_repo=Depends(get_tenant_repo),
    tokens_repo=Depends(get_tokens_repo),
    auth_svc: AuthService = Depends(get_auth_service),
):
    token = request.query_params.get("session_id")
    if not token:
        try:
            body = await request.json()
            if isinstance(body, dict):
                token = body.get("refresh_token") or body.get("session_id")
        except Exception as e:
            try:
                logger.debug("non_json_body_or_parse_error", extra={"error": str(e)})
            except Exception:
                pass
    if not token:
        try:
            form = await request.form()
            form_token = form.get("refresh_token") or form.get("session_id")
            token = form_token if isinstance(form_token, str) else None
        except Exception as e:
            try:
                logger.debug("form_parse_failed", extra={"error": str(e)})
            except Exception:
                pass

    if not token:
        return {"revoked": False, "detail": "refresh token or session_id required"}

    token_hash = auth_svc.hash_refresh_token(token)
    model = await tokens_repo.find_by_token_hash(token_hash)
    if model:
        await tokens_repo.revoke_refresh_token(token_hash)
        cache = get_cache_from_request(request)
        await cache.delete(f"session:{token_hash}")
        if TOKEN_OPERATIONS is not None:
            TOKEN_OPERATIONS.labels(operation="revoke").inc()
    else:
        access_hash = auth_svc.get_token_hash(token)
        cache = get_cache_from_request(request)
        await cache.delete(f"session:{access_hash}")
        from datetime import datetime, timedelta

        expires_at = datetime.utcnow() + timedelta(
            seconds=getattr(auth_svc, "access_token_ttl_seconds", 900)
        )
        await tokens_repo.blacklist_token(None, token, expires_at)
        if TOKEN_OPERATIONS is not None:
            TOKEN_OPERATIONS.labels(operation="revoke").inc()
    return {"revoked": True}


@router.delete("/sessions/{token_hash}")
async def delete_session_by_hash(
    token_hash: str,
    tenant_repo=Depends(get_tenant_repo),
    tokens_repo=Depends(get_tokens_repo),
    auth_svc: AuthService = Depends(get_auth_service),
    request: Request = None,  # type: ignore[assignment]
):
    try:
        model = None
        try:
            model = await tokens_repo.find_by_token_hash(token_hash)
        except Exception as e:
            try:
                logger.debug(
                    "find_by_token_hash_failed",
                    extra={"token_hash": token_hash, "error": str(e)},
                )
            except Exception:
                pass
            model = None
        if not model:
            return {"revoked": False}
        try:
            await tokens_repo.revoke_refresh_token(token_hash)
            if TOKEN_OPERATIONS is not None:
                TOKEN_OPERATIONS.labels(operation="revoke").inc()
        except Exception as e:
            try:
                logger.debug(
                    "revoke_refresh_token_failed",
                    extra={"token_hash": token_hash, "error": str(e)},
                )
            except Exception:
                pass
        try:
            cache = get_cache_from_request(request)
            await cache.delete(f"session:{token_hash}")
        except Exception as e:
            try:
                logger.debug(
                    "cache_delete_failed",
                    extra={"token_hash": token_hash, "error": str(e)},
                )
            except Exception:
                pass
    except Exception as e:
        try:
            logger.exception("delete_session_by_hash_unexpected", extra={"error": str(e)})
        except Exception:
            pass
        return {"revoked": False, "detail": "failed to revoke token"}
    return {"revoked": True}


@router.post("/verify-email")
@router.get("/verify-email")
async def verify_email(
    request: Request,
    token: Optional[str] = None,
    email_tokens_repo=Depends(get_email_tokens_repo),
    user_repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
    db_session=Depends(get_db),
    _rl: None = Depends(require_rate_limit),
):
    """
    Verify user email address using token from email.
    Supports both GET (from email links) and POST (API calls).
    """
    # Support both GET (query param) and POST (JSON body)
    if request.method == "GET":
        token = request.query_params.get("token")
        if not token:
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>Verification Failed</title></head>
                <body>
                    <h1>Verification Failed</h1>
                    <p>Missing verification token.</p>
                </body>
                </html>
                """,
                status_code=400,
            )
    else:
        # POST request - JSON body
        try:
            body = await request.json()
            token = body.get("token")
        except Exception:
            raise HTTPException(status_code=400, detail="invalid request body")

        if not token:
            raise HTTPException(status_code=400, detail="token is required")

    # Consume the email token
    if email_tokens_repo is None:
        if request.method == "GET":
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>Service Unavailable</title></head>
                <body>
                    <h1>Service Unavailable</h1>
                    <p>Email verification service is currently unavailable.</p>
                </body>
                </html>
                """,
                status_code=503,
            )
        raise HTTPException(status_code=503, detail="email verification service unavailable")

    token_svc = EmailTokenService(email_tokens_repo)
    token_data = await token_svc.consume_token(token)

    if not token_data or token_data.get("purpose") != "email_verification":
        if request.method == "GET":
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>Verification Failed</title></head>
                <body>
                    <h1>Verification Failed</h1>
                    <p>The verification link is invalid or has expired.</p>
                </body>
                </html>
                """,
                status_code=400,
            )
        raise HTTPException(status_code=400, detail="invalid or expired token")

    # Mark user as verified
    user_id = token_data.get("user_id")
    if not user_id:
        if request.method == "GET":
            return HTMLResponse(content="<h1>Invalid token data</h1>", status_code=400)
        raise HTTPException(status_code=400, detail="invalid token data")

    user = await user_repo.get_by_id(int(user_id))
    if not user:
        if request.method == "GET":
            return HTMLResponse(content="<h1>User not found</h1>", status_code=404)
        raise HTTPException(status_code=404, detail="user not found")

    # Update user's email_verified status
    await user_repo.update(int(user_id), email_verified=True)

    # Audit log
    await log_audit_event(
        audit_repo,
        user,
        AuditAction.UPDATE,
        AuditResource.USER,
        {"email_verified": True},
        resource_id=int(user_id),
        request=request,
    )

    if request.method == "GET":
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Email Verified</title></head>
            <body>
                <h1>Email Verified Successfully!</h1>
                <p>Your email has been verified. You can now close this window.</p>
            </body>
            </html>
            """
        )

    return {"message": "email verified successfully", "verified": True}


@router.post("/resend-verification")
async def resend_verification_email(
    request: Request,
    email_tokens_repo=Depends(get_email_tokens_repo),
    user_repo=Depends(get_user_repo),
    email_sender=Depends(get_email_sender),
    _rl: None = Depends(require_rate_limit),
):
    """
    Resend email verification link to user.
    Can be called with or without authentication.
    If authenticated, can omit email to use current user's email.
    """
    # Try to get email from request body
    email = None
    try:
        body = await request.json()
        email = body.get("email")
    except Exception:
        pass  # No body or invalid JSON, check if authenticated

    # If no email provided, try to get from current authenticated user
    if not email:
        current_user = getattr(request.state, "current_user", None)
        if current_user and hasattr(current_user, "subject"):
            # Get user by ID to get their email
            user = await user_repo.get_by_id(int(current_user.subject))
            if user:
                email = user.email

    if not email:
        raise HTTPException(status_code=400, detail="email is required")

    # Find user by email
    user = await user_repo.get_by_email_global(email)
    if not user:
        # Don't reveal if user exists or not for security
        return {"message": "if the email exists, a verification link has been sent"}

    # Check if already verified
    if getattr(user, "email_verified", False):
        return {"message": "email already verified"}

    # Generate new token
    if email_tokens_repo is None:
        raise HTTPException(status_code=503, detail="email verification service unavailable")

    token_svc = EmailTokenService(email_tokens_repo)
    token = await token_svc.create_email_verification_token(int(user.id), email)

    # Send verification email
    if email_sender:
        try:
            await email_sender.send_verification(email, token)
        except Exception as e:
            logger.exception("send_verification_failed", extra={"email": email, "error": str(e)})
            raise HTTPException(status_code=500, detail="failed to send verification email")

    return {"message": "verification email sent"}


@router.post("/confirm-email-update")
@router.get("/confirm-email-update")
async def confirm_email_update(
    request: Request,
    token: Optional[str] = None,
    email_tokens_repo=Depends(get_email_tokens_repo),
    user_repo=Depends(get_user_repo),
    audit_repo=Depends(get_audit_repo),
    db_session=Depends(get_db),
    _rl: None = Depends(require_rate_limit),
):
    """
    Confirm email update using token from email.
    Supports both GET (from email links) and POST (API calls).
    """
    # Support both GET (query param) and POST (JSON body)
    if request.method == "GET":
        token = request.query_params.get("token")
        if not token:
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>Email Update Failed</title></head>
                <body>
                    <h1>Email Update Failed</h1>
                    <p>Missing email update token.</p>
                </body>
                </html>
                """,
                status_code=400,
            )
    else:
        # POST request - JSON body
        try:
            body = await request.json()
            token = body.get("token")
        except Exception:
            raise HTTPException(status_code=400, detail="invalid request body")

        if not token:
            raise HTTPException(status_code=400, detail="token is required")

    # Consume the email token
    if email_tokens_repo is None:
        if request.method == "GET":
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>Service Unavailable</title></head>
                <body>
                    <h1>Service Unavailable</h1>
                    <p>Email update service is currently unavailable.</p>
                </body>
                </html>
                """,
                status_code=503,
            )
        raise HTTPException(status_code=503, detail="email update service unavailable")

    token_svc = EmailTokenService(email_tokens_repo)
    token_data = await token_svc.consume_token(token)

    if not token_data or token_data.get("purpose") != "email_update":
        if request.method == "GET":
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>Email Update Failed</title></head>
                <body>
                    <h1>Email Update Failed</h1>
                    <p>The email update link is invalid or has expired.</p>
                </body>
                </html>
                """,
                status_code=400,
            )
        raise HTTPException(status_code=400, detail="invalid or expired token")

    # Update user's email
    user_id = token_data.get("user_id")
    new_email = token_data.get("data", {}).get("new_email")

    if not user_id or not new_email:
        if request.method == "GET":
            return HTMLResponse(content="<h1>Invalid token data</h1>", status_code=400)
        raise HTTPException(status_code=400, detail="invalid token data")

    user = await user_repo.get_by_id(int(user_id))
    if not user:
        if request.method == "GET":
            return HTMLResponse(content="<h1>User not found</h1>", status_code=404)
        raise HTTPException(status_code=404, detail="user not found")

    # Update user's email
    await user_repo.set_email(int(user_id), new_email)

    # Audit log
    await log_audit_event(
        audit_repo,
        user,
        AuditAction.UPDATE,
        AuditResource.USER,
        {"email_updated": True, "new_email": new_email},
        resource_id=int(user_id),
        request=request,
    )

    if request.method == "GET":
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Email Updated</title></head>
            <body>
                <h1>Email Updated Successfully!</h1>
                <p>Your email address has been updated.</p>
            </body>
            </html>
            """
        )

    return {"message": "email updated successfully", "updated": True}
