# backend/app/services/auth_service.py

"""
Authentication business logic: registration, login, token refresh,
logout, and the underlying user/refresh-token persistence operations.

This is the only module that should write to the users and refresh_tokens
tables for auth-related operations — routes call into this service rather
than touching the ORM directly.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import REFRESH_TOKEN_EXPIRE_DAYS, REFRESH_TOKEN_TYPE
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.exceptions import (
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
    TokenRevokedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User


def _hash_token(raw_token: str) -> str:
    """
    Deterministic hash of a refresh token for storage/lookup. SHA-256 is
    used here rather than bcrypt because refresh tokens are already
    high-entropy random JWTs (not user-chosen passwords), so a fast,
    deterministic hash that supports equality lookup by hash is the
    correct tool — bcrypt's per-hash random salt would make lookup by
    token value impossible.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, *, email: str, username: str, password: str) -> User:
    existing_email = await get_user_by_email(db, email)
    if existing_email is not None:
        raise UserAlreadyExistsError(email)

    existing_username = await get_user_by_username(db, username)
    if existing_username is not None:
        raise UserAlreadyExistsError(username)

    password_hash = hash_password(password)
    user = User(
        email=email,
        username=username,
        password_hash=password_hash,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, *, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    if user is None:
        raise InvalidCredentialsError()
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()
    if not user.is_active:
        raise InvalidCredentialsError()
    return user


async def issue_token_pair(db: AsyncSession, user: User) -> tuple[str, str]:
    """
    Creates a new access token and refresh token for the given user,
    persisting a hashed record of the refresh token so it can be
    validated and revoked later.
    """
    access_token = create_access_token(str(user.id))
    refresh_token_value = create_refresh_token(str(user.id))

    token_hash = _hash_token(refresh_token_value)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_token_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(refresh_token_record)
    await db.flush()

    return access_token, refresh_token_value


async def refresh_access_token(db: AsyncSession, raw_refresh_token: str) -> tuple[str, str]:
    """
    Validates a refresh token (signature, expiry, type, and revocation
    status in the database) and issues a new access + refresh token pair.
    The presented refresh token is revoked as part of this call (rotation),
    so a stolen-but-already-used refresh token cannot be replayed.
    """
    payload = decode_token(raw_refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise TokenInvalidError("Refresh token is missing a subject claim.")

    token_hash = _hash_token(raw_refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored_token = result.scalar_one_or_none()

    if stored_token is None:
        raise TokenInvalidError("Refresh token is not recognized.")
    if stored_token.is_revoked:
        raise TokenRevokedError()
    if stored_token.is_expired:
        raise TokenExpiredError("refresh")

    user = await get_user_by_id(db, stored_token.user_id)
    if user is None or not user.is_active:
        raise TokenInvalidError("Refresh token does not correspond to an active user.")

    stored_token.revoked_at = datetime.now(timezone.utc)
    db.add(stored_token)
    await db.flush()

    return await issue_token_pair(db, user)


async def revoke_refresh_token(db: AsyncSession, raw_refresh_token: str) -> None:
    """Logout: revokes a single refresh token. Idempotent — revoking an
    already-revoked or unknown token is treated as a no-op success rather
    than an error, since the end state the caller wants (token unusable)
    is already true."""
    token_hash = _hash_token(raw_refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored_token = result.scalar_one_or_none()

    if stored_token is None or stored_token.is_revoked:
        return

    stored_token.revoked_at = datetime.now(timezone.utc)
    db.add(stored_token)
    await db.flush()


async def revoke_all_refresh_tokens_for_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Revokes every active refresh token for a user. Used for
    'log out everywhere' and password-reset flows."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    tokens = result.scalars().all()
    now = datetime.now(timezone.utc)
    for token in tokens:
        token.revoked_at = now
        db.add(token)
    await db.flush()


async def mark_user_verified(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise UserNotFoundError()
    user.is_verified = True
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def set_user_password(db: AsyncSession, user_id: uuid.UUID, new_password: str) -> User:
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise UserNotFoundError()
    user.password_hash = hash_password(new_password)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user