from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.db import get_db
from app.models.issue import IssueStatus
from app.models.master import Master
from app.models.user import User, UserRole
from app.schemas.issue import MasterRequestRead
from app.schemas.review import ReviewListRead
from app.services import issue as issue_service
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
