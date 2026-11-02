import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, ForeignKey, Enum as SQLEnum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class IssueStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[IssueStatus] = mapped_column(
        SQLEnum(IssueStatus),
        default=IssueStatus.OPEN,
        nullable=False
    )

    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )