from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db import get_db
from app.models.issue import Issue, IssueStatus
from app.models.user import User
from app.schemas.issue import IssueCreate, IssueRead, IssueUpdate
from app.services import issue as issue_service

router = APIRouter(prefix="/issues", tags=["Issues"])


def get_owned_issue(db: Session, issue_id: int, user: User) -> Issue:
    """Return the issue for editing: 404 if it does not exist, 403 if it is not the user's."""
    issue = issue_service.find_issue(db, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    if issue.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed to change this issue")
    return issue


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


@router.get("/{issue_id}", response_model=IssueRead)
def get_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Issue:
    """Return one of the current user's issues."""
    issue = issue_service.get_issue(db, issue_id, current_user)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


@router.patch("/{issue_id}", response_model=IssueRead)
def update_issue(
    issue_id: int,
    data: IssueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Issue:
    """Partially update an issue. Only its owner can do this."""
    issue = get_owned_issue(db, issue_id, current_user)
    try:
        return issue_service.update_issue(db, issue, data)
    except issue_service.CategoryNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Category not found") from exc

@router.delete("/{issue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Soft delete an issue. Only its owner can do this."""
    issue = get_owned_issue(db, issue_id, current_user)
    issue_service.delete_issue(db, issue)
