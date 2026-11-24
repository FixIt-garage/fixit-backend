from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.db import get_db
from app.models.user import User, UserRole
from app.schemas.volunteer import VolunteerRequestDetailRead, VolunteerRequestListRead
from app.services import volunteer as volunteer_service

router = APIRouter(prefix="/volunteer-requests", tags=["Volunteer requests"])
master_required = require_role(UserRole.MASTER)


def volunteer_master(current_user: User = Depends(master_required)) -> User:
    """Only masters who turned on "Я волонтер" can use the volunteer requests."""
    master = current_user.master_profile
    if master is None or not master.is_volunteer:
        raise HTTPException(status_code=403, detail="Only volunteer masters have access")
    return current_user


@router.get("", response_model=VolunteerRequestListRead)
def list_volunteer_requests(
    city: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(volunteer_master),
) -> dict:
    """Open volunteer requests with the progress joined/needed, optionally in one city."""
    return volunteer_service.list_requests(db, current_user, city, limit, offset)


@router.get("/{request_id}", response_model=VolunteerRequestDetailRead)
def get_volunteer_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(volunteer_master),
) -> dict:
    """Request details with the volunteers who have already joined."""
    try:
        return volunteer_service.get_request(db, current_user, request_id)
    except volunteer_service.VolunteerRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Volunteer request not found") from exc
