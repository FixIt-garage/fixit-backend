from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db import get_db
from app.models.issue import Issue, IssueStatus
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
    try:
        return issue_service.create_issue(db, data, current_user)
    except issue_service.CategoryNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Category not found") from exc


@router.get("", response_model=list[IssueRead])
def list_issues(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[IssueStatus | None, Query(alias="status")] = None,
    category_id: Annotated[int | None, Query(ge=1)] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Issue]:
    """List the current user's issues, newest first, with pagination and filters."""
    return issue_service.list_issues(
        db,
        current_user,
        limit=limit,
        offset=offset,
        status=status_filter,
        category_id=category_id,
    )
