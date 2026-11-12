from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.issue import Issue
from app.models.master import Master
from app.models.order import Order
from app.models.review import Review
from app.models.user import User, UserRole
from app.schemas.user import UserProfileResponse, UserStats


def count_requests(db: Session, user: User) -> int:
    """The user's own issues, without soft-deleted ones."""
    query = (
        select(func.count())
        .select_from(Issue)
        .where(Issue.owner_id == user.id, Issue.deleted_at.is_(None))
    )
    return db.scalar(query) or 0


def count_reviews(db: Session, user: User) -> int:
    """Masters: reviews they received. Everyone else: reviews they wrote."""
    query = select(func.count()).select_from(Review).join(Order, Order.id == Review.order_id)
    if user.role == UserRole.MASTER:
        query = query.join(Master, Master.id == Order.master_id).where(Master.user_id == user.id)
    else:
        query = query.where(Order.client_id == user.id)
    return db.scalar(query) or 0


def get_profile(db: Session, user: User) -> UserProfileResponse:
    return UserProfileResponse(
        id=user.id,
        public_id=user.public_id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        address=user.address,
        city=user.city,
        avatar_url=user.avatar_url,
        role=user.role,
        stats=UserStats(
            requests_count=count_requests(db, user),
            reviews_count=count_reviews(db, user),
            member_since_year=user.created_at.year,
        ),
    )
