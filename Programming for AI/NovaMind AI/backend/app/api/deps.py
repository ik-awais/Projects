# backend/app/api/deps.py
"""
Shared FastAPI dependencies: database session injection and current-user
resolution from a bearer access token. Every authenticated route depends
on get_current_user (or get_current_active_user) from this module.
"""

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ACCESS_TOKEN_TYPE
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.exceptions import AuthError, TokenInvalidError, UserNotFoundError
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=True)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Per-request database session. Commits on clean exit, rolls back on
    exception, always closes.
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Resolves the authenticated User from a Bearer access token. Raises
    AuthError subclasses (mapped to 401 by main.py's exception handler)
    for any invalid, expired, or unrecognized token.
    """
    token = credentials.credentials
    payload = decode_token(token, expected_type=ACCESS_TOKEN_TYPE)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise TokenInvalidError("Access token is missing a subject claim.")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as exc:
        raise TokenInvalidError("Access token subject is not a valid user id.") from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise UserNotFoundError()

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Same as get_current_user, but additionally rejects deactivated
    accounts. Use this (not get_current_user) on routes that should be
    unreachable by a disabled account."""
    if not current_user.is_active:
        raise AuthError("This account has been deactivated.")
    return current_user