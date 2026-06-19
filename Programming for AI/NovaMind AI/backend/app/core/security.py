# backend/app/core/security.py

"""
JWT token creation/verification and password hashing.
Used exclusively by auth_service.py and api/deps.py — no other module
should construct or decode tokens directly.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.constants import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ACCESS_TOKEN_TYPE,
    BCRYPT_ROUNDS,
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS,
    EMAIL_VERIFICATION_TOKEN_TYPE,
    JWT_ALGORITHM,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
    PASSWORD_RESET_TOKEN_TYPE,
    REFRESH_TOKEN_EXPIRE_DAYS,
    REFRESH_TOKEN_TYPE,
)
from app.core.config import settings
from app.exceptions import TokenExpiredError, TokenInvalidError, WeakPasswordError


# ── Password hashing ──────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """Hash a plaintext password with bcrypt. Raises WeakPasswordError if it
    fails minimum strength requirements."""
    validate_password_strength(plain_password)
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash. Returns False on
    any malformed-hash error rather than raising, so callers can treat it
    as a simple boolean check."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_password_strength(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise WeakPasswordError(f"must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise WeakPasswordError(f"must be at most {PASSWORD_MAX_LENGTH} characters long.")
    if not any(char.isdigit() for char in password):
        raise WeakPasswordError("must contain at least one digit.")
    if not any(char.isalpha() for char in password):
        raise WeakPasswordError("must contain at least one letter.")


# ── JWT token creation ────────────────────────────────────────────────────

def _create_token(
    *,
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: str, *, extra_claims: dict[str, Any] | None = None) -> str:
    return _create_token(
        subject=user_id,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims=extra_claims,
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )


def create_email_verification_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        token_type=EMAIL_VERIFICATION_TOKEN_TYPE,
        expires_delta=timedelta(hours=EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
    )


def create_password_reset_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        token_type=PASSWORD_RESET_TOKEN_TYPE,
        expires_delta=timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )


# ── JWT token verification ────────────────────────────────────────────────

def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    """
    Decode and validate a JWT. Raises TokenExpiredError or TokenInvalidError
    (both subclasses of AuthError) rather than letting jose's JWTError leak
    out of this module.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError(expected_type or "access") from exc
    except JWTError as exc:
        raise TokenInvalidError(f"Could not validate token: {exc}") from exc

    if expected_type is not None and payload.get("type") != expected_type:
        raise TokenInvalidError(
            f"Expected a '{expected_type}' token but received a '{payload.get('type')}' token."
        )

    return payload


def get_subject_from_token(token: str, *, expected_type: str | None = None) -> str:
    payload = decode_token(token, expected_type=expected_type)
    subject = payload.get("sub")
    if not subject:
        raise TokenInvalidError("Token is missing a subject claim.")
    return subject