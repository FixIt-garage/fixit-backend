from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a password using the recommended password hashing algorithm."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its stored hash."""
    return password_hash.verify(password, hashed_password)



def create_access_token(subject: str) -> str:
    """Create a short-lived JWT access token with a unique identifier."""
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "jti": str(uuid4()),
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )



def create_refresh_token(subject: str) -> str:
    """Create a long-lived JWT refresh token."""
    expires_at = datetime.now(UTC) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "refresh",
        "jti": str(uuid4()),
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    return payload