from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.db import get_db
from app.models.issue import IssueStatus
from app.models.user import User, UserRole
from app.schemas.issue import MasterRequestRead
from app.services import issue as issue_service

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
