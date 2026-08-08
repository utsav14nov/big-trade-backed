"""Auth endpoints. Access token in body (short-lived), refresh token in httpOnly cookie."""
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from jose import JWTError
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    verify_password, create_access_token, create_refresh_token, decode_token,
)
from app.db.session import get_db
from app.models.models import User, RefreshToken
from app.schemas.schemas import LoginRequest, TokenResponse, UserOut
from app.api.deps import get_current_user
from app.services.audit import log_action

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

REFRESH_COOKIE = "mandi_refresh"
LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 15


def _set_refresh_cookie(resp: Response, token: str):
    resp.set_cookie(
        key=REFRESH_COOKIE, value=token, httponly=True,
        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN, path="/auth",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)   # brute-force protection
async def login(request: Request, body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    # Constant-ish behaviour whether or not the user exists (avoid user enumeration)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=423, detail="Account temporarily locked. Try again later.")

    if not verify_password(body.password, user.hashed_password):
        user.failed_logins += 1
        if user.failed_logins >= LOCKOUT_THRESHOLD:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_logins = 0
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # success
    user.failed_logins = 0
    user.locked_until = None
    access = create_access_token(str(user.id), user.role.value)
    refresh, jti = create_refresh_token(str(user.id))
    db.add(RefreshToken(
        jti=uuid.UUID(jti), user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    await log_action(db, user.id, "auth.login", "user", str(user.id), request)
    await db.commit()

    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = decode_token(token, expected_type="refresh")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    jti = uuid.UUID(payload["jti"])
    record = await db.get(RefreshToken, jti)
    if record is None or record.revoked or record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    # rotate: revoke old, issue new (detects token theft/replay)
    record.revoked = True
    new_refresh, new_jti = create_refresh_token(str(user.id))
    db.add(RefreshToken(
        jti=uuid.UUID(new_jti), user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    await db.commit()

    access = create_access_token(str(user.id), user.role.value)
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        try:
            payload = decode_token(token, expected_type="refresh")
            record = await db.get(RefreshToken, uuid.UUID(payload["jti"]))
            if record:
                record.revoked = True
                await db.commit()
        except JWTError:
            pass
    response.delete_cookie(REFRESH_COOKIE, path="/auth")
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
