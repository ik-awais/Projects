# backend/app/api/v1/auth.py  
"""
Authentication API routes: register, login, refresh, logout.

Email verification and password reset endpoints are intentionally not
included in this batch — they require the SMTP-sending capability that
has not been generated yet (no future-file imports, per project rules).
They will be added as a small follow-up batch once an email service
module exists.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db_session
from app.core.security import decode_token
from app.models.user import User
from app.schemas.auth import (
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    TokenPairResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import (
    authenticate_user,
    get_user_by_id,
    issue_token_pair,
    refresh_access_token,
    register_user,
    revoke_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenPairResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenPairResponse:
    user = await register_user(
        db,
        email=payload.email,
        username=payload.username,
        password=payload.password,
    )
    access_token, refresh_token = await issue_token_pair(db, user)
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenPairResponse)
async def login(
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenPairResponse:
    user = await authenticate_user(db, email=payload.email, password=payload.password)
    access_token, refresh_token = await issue_token_pair(db, user)
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenPairResponse:
    access_token, new_refresh_token = await refresh_access_token(db, payload.refresh_token)

    access_payload = decode_token(access_token, expected_type="access")
    user = await get_user_by_id(db, uuid.UUID(access_payload["sub"]))

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    await revoke_refresh_token(db, payload.refresh_token)
    return MessageResponse(message="Successfully logged out.")


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)