import hashlib
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import decode_access_token, get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer()

def _hash_refresh_token(token: str) -> str:
    """Return a SHA-256 hash of a refresh token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_token_pair(user: User, db: Session) -> TokenResponse:
    """Create access and refresh tokens and store the refresh token hash."""
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    payload = decode_token(refresh_token)
    expires_at = datetime.fromtimestamp(
        float(payload["exp"]),
        tz=timezone.utc,
    )

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh_token(refresh_token),
            expires_at=expires_at,
        )
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Register a new user and return a token pair."""
    existing_user = db.scalar(
        select(User).where(User.email == str(request.email))
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=str(request.email),
        password_hash=hash_password(request.password),
        first_name=request.first_name,
        last_name=request.last_name,
        role=request.role,
    )

    db.add(user)
    db.flush()

    tokens = _create_token_pair(user, db)
    db.commit()

    return tokens


@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate a user and return a token pair."""
    user = db.scalar(
        select(User).where(User.email == str(request.email))
    )

    if (
        user is None
        or not verify_password(request.password, user.password_hash)
        or not user.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tokens = _create_token_pair(user, db)
    db.commit()

    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: RefreshRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Rotate a refresh token and issue a new token pair."""
    try:
        payload = decode_token(request.refresh_token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )

    token_hash = _hash_refresh_token(request.refresh_token)

    stored_token = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
    )

    now = datetime.now(timezone.utc)

    if (
        stored_token is None
        or stored_token.revoked_at is not None
        or stored_token.expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or has been revoked",
        )

    user = db.scalar(select(User).where(User.id == int(subject)))

    if user is None or not user.is_active or stored_token.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    stored_token.revoked_at = now
    tokens = _create_token_pair(user, db)
    db.commit()

    return tokens


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: RefreshRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Revoke a refresh token."""
    token_hash = _hash_refresh_token(request.refresh_token)

    stored_token = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )

    if stored_token is not None and stored_token.revoked_at is None:
        stored_token.revoked_at = datetime.now(timezone.utc)
        db.commit()

    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the current authenticated user."""
    return current_user


@router.get("/token-check", response_model=MessageResponse)
def token_check(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> MessageResponse:
    """Validate an access token."""
    decode_access_token(credentials.credentials)
    return MessageResponse(message="Access token is valid")