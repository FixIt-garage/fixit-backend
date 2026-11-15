import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReviewTag(enum.StrEnum):
    ON_TIME = "Вчасно"
    QUALITY = "Якісно"
    POLITE = "Ввічливо"
    FAIR_PRICE = "Чесна ціна"
    CLEANED_UP = "Прибрав за собою"

class Review(Base):
    """Client review of a completed issue."""

    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "rating BETWEEN 1 AND 5",
                    name="ck_reviews_rating_range",
        ),
        CheckConstraint(
            """
            (master_id IS NOT NULL AND company_id IS NULL)
            OR
            (master_id IS NULL AND company_id IS NOT NULL)
            """,
            name="ck_reviews_exactly_one_target",
        ),
        UniqueConstraint("issue_id", name="uq_reviews_issue_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    master_id: Mapped[int | None] = mapped_column(
        ForeignKey("masters.id"),
        nullable=True,
    )
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"),
        nullable=True,
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
