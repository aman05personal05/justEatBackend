import hashlib
import os
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, get_password_hash, verify_password
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.refresh_token import RefreshToken
from app.models.user import CustomerProfile, OwnerProfile, User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LogoutRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenPair,
    UserCreate,
    UserLogin,
    UserOut,
)
from app.schemas.common import AddedToFavouritesResponse, ForgotPasswordResponse, MessageResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        logger.warning("register_email_exists", email=payload.email)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(email=payload.email, hashed_password=get_password_hash(payload.password), role=payload.role)
    db.add(user)
    await db.flush()  # get user.id before creating the profile

    if payload.role.value == "owner":
        db.add(OwnerProfile(user_id=user.id, full_name=payload.full_name, phone=payload.phone))
    else:
        db.add(CustomerProfile(user_id=user.id, full_name=payload.full_name, phone=payload.phone))

    await db.commit()
    await db.refresh(user)
    logger.info("user_registered", user_id=user.id, email=user.email, role=user.role.value)
    return user


@router.post("/token", response_model=TokenPair, include_in_schema=False)
async def token(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        logger.warning("login_failed", email=form.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password",
                            headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        logger.warning("login_inactive_account", user_id=user.id, email=form.username)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    access_token = create_access_token(subject=str(user.id), role=user.role.value, email=user.email)
    raw_refresh, token_hash, expires_at = create_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()
    logger.info("user_logged_in", user_id=user.id, email=user.email)
    return TokenPair(access_token=access_token, refresh_token=raw_refresh)


@router.post("/login", response_model=TokenPair)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        logger.warning("login_failed", email=payload.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password",
                            headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        logger.warning("login_inactive_account", user_id=user.id, email=payload.email)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    access_token = create_access_token(subject=str(user.id), role=user.role.value, email=user.email)
    raw_refresh, token_hash, expires_at = create_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()
    logger.info("user_logged_in", user_id=user.id, email=user.email)
    return TokenPair(access_token=access_token, refresh_token=raw_refresh)


@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    rt = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.revoked.is_(False))
    )
    if not rt or rt.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        logger.warning("refresh_token_invalid")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = await db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    rt.revoked = True
    new_access = create_access_token(subject=str(user.id), role=user.role.value, email=user.email)
    raw_new, new_hash, new_expires = create_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=new_hash, expires_at=new_expires))
    await db.commit()
    logger.info("token_refreshed", user_id=user.id)
    return TokenPair(access_token=new_access, refresh_token=raw_new)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    rt = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if rt:
        rt.revoked = True
        await db.commit()
        logger.info("user_logged_out", user_id=rt.user_id)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user and user.is_active:
        raw_token = os.urandom(32).hex()
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        user.reset_token_hash = token_hash
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.commit()
        if settings.DEBUG:
            return {
                "message": "Password reset token generated",
                "reset_token": raw_token,
                "note": "In production this token would be sent by email, not returned here",
            }
    # Always return the same message to prevent user enumeration
    return {"message": "If that email is registered, you will receive reset instructions shortly"}


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    user = await db.scalar(select(User).where(User.reset_token_hash == token_hash))
    if not user or not user.reset_token_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    expires = user.reset_token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user.hashed_password = get_password_hash(payload.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    # Revoke all refresh tokens for security
    refresh_tokens = (await db.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
    )).all()
    for rt in refresh_tokens:
        rt.revoked = True
    await db.commit()
    logger.info("password_reset", user_id=user.id)
    return {"message": "Password updated successfully. Please log in with your new password."}


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return current_user


@router.post("/change-password", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        logger.warning("change_password_wrong_current", user_id=current_user.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.hashed_password = get_password_hash(payload.new_password)
    await db.commit()
    logger.info("password_changed", user_id=current_user.id)
    return {"message": "Password changed successfully"}
