from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Category
from app.models.issue import Issue, IssueStatus
from app.models.user import User
from app.schemas.issue import IssueCreate, IssueUpdate


class CategoryNotFoundError(Exception):
    """Raised when an issue refers to a category that does not exist."""


def create_issue(db: Session, data: IssueCreate, owner: User) -> Issue:
    """Create an issue owned by the given user."""
    if db.get(Category, data.category_id) is None:
        raise CategoryNotFoundError(data.category_id)

    issue = Issue(**data.model_dump(), owner_id=owner.id)
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


def list_issues(
    db: Session,
    owner: User,
    *,
    limit: int,
    offset: int,
    status: IssueStatus | None = None,
    category_id: int | None = None,
) -> list[Issue]:
    """Return the owner's issues, newest first, with optional filters and pagination."""
    query = select(Issue).where(Issue.owner_id == owner.id, Issue.deleted_at.is_(None))

    if status is not None:
        query = query.where(Issue.status == status)
    if category_id is not None:
        query = query.where(Issue.category_id == category_id)

    query = query.order_by(Issue.created_at.desc(), Issue.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(query))


def get_issue(db: Session, issue_id: int, owner: User) -> Issue | None:
    """Return the owner's non-deleted issue by id, or None if there is no such issue."""
    return db.scalar(
        select(Issue).where(
            Issue.id == issue_id,
            Issue.owner_id == owner.id,
            Issue.deleted_at.is_(None),
        )
    )


def find_issue(db: Session, issue_id: int) -> Issue | None:
    """Return a non-deleted issue by id regardless of its owner."""
    return db.scalar(select(Issue).where(Issue.id == issue_id, Issue.deleted_at.is_(None)))


def update_issue(db: Session, issue: Issue, data: IssueUpdate) -> Issue:
    """Apply only the fields that were sent in the request."""
    changes = data.model_dump(exclude_unset=True)

    category_id = changes.get("category_id")
    if category_id is not None and db.get(Category, category_id) is None:
        raise CategoryNotFoundError(category_id)

    for field, value in changes.items():
        setattr(issue, field, value)
    db.commit()
    db.refresh(issue)
    return issue


def delete_issue(db: Session, issue: Issue) -> None:
    """Soft delete: mark the issue as deleted instead of removing the row."""
    issue.deleted_at = datetime.now(UTC)
    db.commit()
    