import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IssueStatus(enum.StrEnum):
    """Request flow: sent -> accepted -> in_progress -> done (or declined / cancelled)."""

    SENT = "sent"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DECLINED = "declined"
    CANCELLED = "cancelled"


ISSUE_STATUS_TYPE = SQLEnum(
    IssueStatus,
    name="issuestatus",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        CheckConstraint(
            "assignee_master_id IS NULL OR assignee_company_id IS NULL",
            name="ck_issues_single_assignee",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    status: Mapped[IssueStatus] = mapped_column(
        ISSUE_STATUS_TYPE,
        default=IssueStatus.SENT,
        nullable=False,
    )

    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    assignee_master_id: Mapped[int | None] = mapped_column(
        ForeignKey("masters.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    assignee_company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    review_company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
