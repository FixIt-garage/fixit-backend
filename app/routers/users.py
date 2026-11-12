from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.user import UserProfileResponse, UserUpdate
from app.services import user as user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """Return the current user's profile with stats."""
    return user_service.get_profile(db, current_user)


@router.patch("/me", response_model=UserProfileResponse)
def update_my_profile(
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """Partially update the current user's profile."""
    try:
        return user_service.update_profile(db, current_user, data)
    except user_service.PhoneTakenError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this phone already exists",
        ) from exc
