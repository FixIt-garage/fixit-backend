from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.issue import ISSUE_STATUS_TYPE, IssueStatus


class IssueStatusEvent(Base):
    """A single status change in an issue's timeline."""

    __tablename__ = "issue_status_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    status: Mapped[IssueStatus] = mapped_column(
        ISSUE_STATUS_TYPE,
        nullable=False,
    )

    actor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
