from sqlalchemy.orm import Session

from app.models.issue import Issue
from app.models.user import User
from app.schemas.issue import IssueCreate


def create_issue(db: Session, data: IssueCreate, owner: User) -> Issue:
    """Create an issue owned by the given user."""
    issue = Issue(**data.model_dump(), owner_id=owner.id)
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue
