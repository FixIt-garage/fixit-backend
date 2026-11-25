from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db import get_db
from app.models.issue import Issue, IssueStatus
from app.models.user import User
from app.schemas.issue import (
    IssueCreate,
    IssueDetailRead,
    IssueListRead,
    IssueRead,
    IssueUpdate,
)
from app.schemas.pagination import Page, PageParams
from app.schemas.review import ReviewCreate, ReviewRead
from app.services import issue as issue_service
from app.services import review as review_service

router = APIRouter(prefix="/issues", tags=["Issues"])


def get_owned_issue(db: Session, issue_id: int, user: User) -> Issue:
    """Return the issue for editing: 404 if it does not exist, 403 if it is not the user's."""
    issue = issue_service.find_issue(db, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    if issue.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed to change this issue")
    return issue


def change_issue_status(
    issue_id: int,
    target_status: IssueStatus,
    db: Session,
    current_user: User,
) -> Issue:
    """Apply a status transition and translate service errors into HTTP errors."""
    try:
        return issue_service.transition_issue(
            db,
            issue_id,
            current_user,
            target_status,
        )
    except issue_service.IssueNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        ) from exc
    except issue_service.IssuePermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc
    except issue_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


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
    except issue_service.MasterNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Master not found") from exc
    except issue_service.CompanyNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Service center not found") from exc


@router.get("", response_model=IssueListRead | Page[IssueRead])
def list_issues(
    params: Annotated[PageParams, Depends()],
    status_filter: Annotated[IssueStatus | None, Query(alias="status")] = None,
    category_id: Annotated[int | None, Query(ge=1)] = None,
    mine: bool = False,
    status_group: Annotated[str | None, Query(pattern="^(active|done)$")] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueListRead | Page[IssueRead]:
    """List the current user's issues, newest first.

    With ``mine=true`` the response also has the counts for the status tabs.
    """
    if mine:
        if status_filter is not None:
            raise HTTPException(
                status_code=422,
                detail="Use status_group instead of status with mine=true",
            )

        issues, counts = issue_service.list_my_issues(
            db,
            current_user,
            limit=params.limit,
            offset=params.offset,
            status_group=status_group,
            category_id=category_id,
        )
        return IssueListRead(
            items=[IssueRead.model_validate(issue) for issue in issues],
            total=counts[status_group or "all"],
            limit=params.limit,
            offset=params.offset,
            counts=counts,
        )

    if status_group is not None:
        raise HTTPException(
            status_code=422,
            detail="status_group requires mine=true",
        )

    items, total = issue_service.list_issues(
        db,
        current_user,
        limit=params.limit,
        offset=params.offset,
        status=status_filter,
        category_id=category_id,
    )
    return Page[IssueRead](
        items=[IssueRead.model_validate(item) for item in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.post("/{issue_id}/accept", response_model=IssueRead)
def accept_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Issue:
    """Accept an assigned issue."""
    return change_issue_status(issue_id, IssueStatus.ACCEPTED, db, current_user)


@router.post("/{issue_id}/decline", response_model=IssueRead)
def decline_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Issue:
    """Decline an assigned issue."""
    return change_issue_status(issue_id, IssueStatus.DECLINED, db, current_user)


@router.post("/{issue_id}/start", response_model=IssueRead)
def start_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Issue:
    """Start working on an accepted issue."""
    return change_issue_status(issue_id, IssueStatus.IN_PROGRESS, db, current_user)


@router.post("/{issue_id}/complete", response_model=IssueRead)
def complete_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Issue:
    """Complete an issue in progress."""
    return change_issue_status(issue_id, IssueStatus.DONE, db, current_user)


@router.post("/{issue_id}/cancel", response_model=IssueRead)
def cancel_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Issue:
    """Cancel an issue owned by the current user."""
    return change_issue_status(issue_id, IssueStatus.CANCELLED, db, current_user)


@router.get("/{issue_id}", response_model=IssueDetailRead)
def get_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueDetailRead:
    """Return issue details with status timeline and assigned master."""
    details = issue_service.get_issue_details(db, issue_id, current_user)

    if details is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    issue, timeline, assigned_master, master_user = details

    master_data = None
    if assigned_master is not None and master_user is not None:
        master_data = {
            "name": f"{master_user.first_name} {master_user.last_name}",
            "rating": assigned_master.rating,
        }

    return IssueDetailRead(
        **IssueRead.model_validate(issue).model_dump(),
        timeline=timeline,
        assigned_master=master_data,
    )


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


@router.post(
    "/{issue_id}/review",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
)
def create_issue_review(
    issue_id: int,
    data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Leave a review for a completed issue owned by the current user."""
    try:
        review = review_service.create_review(
            db,
            issue_id,
            current_user,
            data,
        )
    except review_service.IssueNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Issue not found") from exc
    except review_service.ReviewPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (
        review_service.IssueNotCompletedError,
        review_service.ReviewAlreadyExistsError,
        review_service.ReviewTargetNotFoundError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "id": review.id,
        "issue_id": review.issue_id,
        "master_id": review.master_id,
        "company_id": review.company_id,
        "rating": review.rating,
        "tags": review.tags,
        "comment": review.comment,
        "created_at": review.created_at,
        "author_first_name": current_user.first_name,
        "author_last_name": current_user.last_name,
        "author_avatar_url": current_user.avatar_url,
    }