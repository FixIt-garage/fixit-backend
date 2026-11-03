from sqlalchemy.orm import Session

from app.models.catalog import Category
from app.models.issue import Issue
from app.models.user import User
from app.schemas.issue import IssueCreate


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
