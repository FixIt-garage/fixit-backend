from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db import get_db
from app.models.issue import Issue
from app.models.user import User
from app.schemas.issue import IssueCreate, IssueRead
from app.services import issue as issue_service

router = APIRouter(prefix="/issues", tags=["Issues"])


@router.post("", response_model=IssueRead, status_code=status.HTTP_201_CREATED)
def create_issue(
    data: IssueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Issue:
    """Create an issue owned by the current user."""
    return issue_service.create_issue(db, data, current_user)
