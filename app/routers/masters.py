from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.db import get_db
from app.models.issue import IssueStatus
from app.models.master import Master
from app.models.user import User, UserRole
from app.schemas.issue import MasterRequestRead
from app.schemas.master import (
    MasterProfileRead,
    MasterProfileUpdate,
    MasterPublicRead,
    MasterVolunteerUpdate,
)
from app.schemas.review import ReviewListRead
from app.services import issue as issue_service
from app.services import master as master_service
from app.services import review as review_service

router = APIRouter(prefix="/masters", tags=["Masters"])
master_required = require_role(UserRole.MASTER)


@router.get("/me/requests", response_model=list[MasterRequestRead])
def get_my_requests(
    status_filter: Annotated[IssueStatus | None, Query(alias="status")] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(master_required),
) -> list[dict]:
    """Return requests assigned to the current master or their service center."""
    return issue_service.list_master_requests(
        db,
        current_user,
        status=status_filter,
    )


@router.patch("/me", response_model=MasterProfileRead)
def update_my_profile(
    data: MasterProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(master_required),
) -> MasterProfileRead:
    """Partially save the current master's profile (the form can be finished later)."""
    try:
        return master_service.update_profile(db, current_user, data)
    except master_service.CategoryNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Category not found") from exc


@router.patch("/me/volunteer", response_model=MasterProfileRead)
def update_my_volunteer_flag(
    data: MasterVolunteerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(master_required),
) -> MasterProfileRead:
    """Toggle "Я волонтер" for the current master."""
    return master_service.set_volunteer(db, current_user, data.is_volunteer)


@router.get(
    "/{master_id}",
    response_model=MasterPublicRead,
    dependencies=[Depends(get_current_user)],
)
def get_master(
    master_id: int,
    db: Session = Depends(get_db),
) -> MasterPublicRead:
    """Return the public profile of a master (any logged-in user can open it)."""
    try:
        return master_service.get_public_profile(db, master_id)
    except master_service.MasterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Master not found") from exc


@router.get("/{master_id}/reviews", response_model=ReviewListRead)
def get_master_reviews(
    master_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """Return paginated reviews received by a master."""
    if db.get(Master, master_id) is None:
        raise HTTPException(status_code=404, detail="Master not found")

    return review_service.list_reviews(
        db,
        master_id=master_id,
        limit=limit,
        offset=offset,
    )