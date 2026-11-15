from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.issue import Issue, IssueStatus
from app.models.master import Master
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewCreate


class IssueNotFoundError(Exception):
    """The issue does not exist."""


class ReviewPermissionError(Exception):
    """The current user cannot review this issue."""


class IssueNotCompletedError(Exception):
    """Reviews are allowed only for completed issues."""


class ReviewAlreadyExistsError(Exception):
    """The issue already has a review."""


class ReviewTargetNotFoundError(Exception):
    """The master or service center being reviewed does not exist."""


def create_review(
    db: Session,
    issue_id: int,
    author: User,
    data: ReviewCreate,
) -> Review:
    """Create one review for a completed issue and update its target rating."""

    issue = db.scalar(
        select(Issue)
        .where(
            Issue.id == issue_id,
            Issue.deleted_at.is_(None),
        )
        .with_for_update()
    )

    if issue is None:
        raise IssueNotFoundError(issue_id)

    if issue.owner_id != author.id:
        raise ReviewPermissionError("Only the issue owner can leave a review")

    if issue.status != IssueStatus.DONE:
        raise IssueNotCompletedError("Only completed issues can be reviewed")

    existing_review = db.scalar(
        select(Review.id).where(Review.issue_id == issue.id)
    )
    if existing_review is not None:
        raise ReviewAlreadyExistsError(issue.id)

    if issue.review_target_unknown:
        raise ReviewTargetNotFoundError(
            "The original review target is unknown"
        )

    master = None
    company = None

    if issue.review_company_id is not None:
        company = db.scalar(
            select(Company)
            .where(Company.id == issue.review_company_id)
            .with_for_update()
        )
        if company is None:
            raise ReviewTargetNotFoundError("Service center not found")

    elif issue.assignee_master_id is not None:
        master = db.scalar(
            select(Master)
            .where(Master.id == issue.assignee_master_id)
            .with_for_update()
        )
        if master is None:
            raise ReviewTargetNotFoundError("Master not found")

    else:
        raise ReviewTargetNotFoundError("The issue has no review target")

    review = Review(
        issue_id=issue.id,
        author_id=author.id,
        master_id=master.id if master is not None else None,
        company_id=company.id if company is not None else None,
        rating=data.rating,
        tags=[tag.value for tag in data.tags],
        comment=data.comment,
    )
    db.add(review)
    db.flush()

    if master is not None:
        rating_query = select(
            func.avg(Review.rating),
            func.count(Review.id),
        ).where(Review.master_id == master.id)

        master.rating, master.reviews_count = db.execute(rating_query).one()

    else:
        rating_query = select(
            func.avg(Review.rating),
            func.count(Review.id),
        ).where(Review.company_id == company.id)

        company.rating, company.reviews_count = db.execute(rating_query).one()

    db.commit()
    db.refresh(review)
    return review

def list_reviews(
    db: Session,
    *,
    master_id: int | None = None,
    company_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Return paginated reviews for a master or service center."""

    if (master_id is None) == (company_id is None):
        raise ValueError("Specify exactly one review target")

    filters = (
        [Review.master_id == master_id]
        if master_id is not None
        else [Review.company_id == company_id]
    )

    total = db.scalar(
        select(func.count(Review.id)).where(*filters)
    ) or 0

    rows = db.execute(
        select(
            Review,
            User.first_name,
            User.last_name,
            User.avatar_url,
        )
        .join(User, User.id == Review.author_id)
        .where(*filters)
        .order_by(Review.created_at.desc(), Review.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    items = [
        {
            "id": review.id,
            "issue_id": review.issue_id,
            "master_id": review.master_id,
            "company_id": review.company_id,
            "rating": review.rating,
            "tags": review.tags,
            "comment": review.comment,
            "created_at": review.created_at,
            "author_first_name": first_name,
            "author_last_name": last_name,
            "author_avatar_url": avatar_url,
        }
        for review, first_name, last_name, avatar_url in rows
    ]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }