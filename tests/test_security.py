from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import settings
from app.core.dependencies import decode_access_token
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing():
    password = "TestPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("WrongPassword123!", hashed)


def test_access_token():
    token = create_access_token("user-123")
    payload = decode_token(token)

    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert decode_access_token(token) == "user-123"


def test_refresh_token():
    token = create_refresh_token("user-123")
    payload = decode_token(token)

    assert payload["sub"] == "user-123"
    assert payload["type"] == "refresh"

def test_expired_token_rejected():
    expired_token = jwt.encode(
        {
            "sub": "user-123",
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired_token)
