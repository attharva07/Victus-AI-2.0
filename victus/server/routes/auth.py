from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from ..db import UserRecord
from ..rate_limit import RateLimitResult
from ..schemas import LoginRequest, MFAEnrollResponse, MFAVerifyRequest, RegisterRequest, TokenResponse, UserResponse
from ..security import (
    build_token_payload,
    create_access_token,
    decode_totp_secret,
    encode_totp_secret,
    generate_totp_secret,
    hash_password,
    verify_password,
    verify_totp,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _rate_limit_or_raise(request: Request, label: str) -> RateLimitResult:
    limiter = request.app.state.rate_limiter
    key = f"{label}:{_client_ip(request)}"
    result = limiter.check(key)
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(result.reset_after)},
        )
    return result


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/register", response_model=UserResponse)
async def register(request: Request, payload: RegisterRequest) -> UserResponse:
    _rate_limit_or_raise(request, "register")
    settings = request.app.state.settings
    db = request.app.state.db

    if not settings.allow_registration and db.count_users() > 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled")

    email = payload.email.lower()
    if "@" not in email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email")
    if db.get_user_by_email(email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    is_admin = False
    if not settings.allow_registration and db.count_users() == 0:
        is_admin = True

    now = datetime.now(timezone.utc).isoformat()
    user = UserRecord(
        user_id=str(uuid4()),
        email=email,
        password_hash=hash_password(payload.password),
        is_admin=is_admin,
        created_at=now,
        mfa_secret=None,
        mfa_enabled=False,
    )
    db.create_user(user)
    return UserResponse(
        id=user.user_id,
        email=user.email,
        is_admin=user.is_admin,
        mfa_enabled=user.mfa_enabled,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, payload: LoginRequest) -> TokenResponse:
    _rate_limit_or_raise(request, "login")
    settings = request.app.state.settings
    db = request.app.state.db

    email = payload.email.lower()
    user = db.get_user_by_email(email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.mfa_enabled:
        if not payload.totp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA code required")
        if not user.mfa_secret:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA misconfigured")
        secret = decode_totp_secret(user.mfa_secret, settings.mfa_secret_key)
        if not verify_totp(secret, payload.totp):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")

    payload_data = build_token_payload(user.user_id, user.email, settings.token_ttl_seconds)
    token = create_access_token(payload_data, settings.token_secret)
    return TokenResponse(token=token)


@router.post("/mfa/enroll", response_model=MFAEnrollResponse)
async def enroll_mfa(request: Request) -> MFAEnrollResponse:
    settings = request.app.state.settings
    db = request.app.state.db
    user = request.state.user
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    secret = generate_totp_secret()
    encoded = encode_totp_secret(secret, settings.mfa_secret_key)
    db.update_mfa_secret(user.user_id, encoded)
    otpauth_url = f"otpauth://totp/Victus:{user.email}?secret={secret}&issuer=Victus"
    return MFAEnrollResponse(secret=secret, otpauth_url=otpauth_url)


@router.post("/mfa/verify")
async def verify_mfa(request: Request, payload: MFAVerifyRequest) -> dict:
    settings = request.app.state.settings
    db = request.app.state.db
    user = request.state.user
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA not enrolled")
    secret = decode_totp_secret(user.mfa_secret, settings.mfa_secret_key)
    if not verify_totp(secret, payload.code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
    db.set_mfa_enabled(user.user_id, True)
    return {"ok": True, "mfa_enabled": True}
