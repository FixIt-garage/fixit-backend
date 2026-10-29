import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class VolunteerOrganization(Base):
    """Volunteer / charity organization, registered by a user (its representative)."""

    __tablename__ = "volunteer_organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(String(255))
    contact: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User")
    requests = relationship("VolunteerRequest", back_populates="organization")


class VolunteerRequestStatus(enum.StrEnum):
    open = "open"
    closed = "closed"


class VolunteerRequest(Base):
    """A call for volunteers published by an organization."""

    __tablename__ = "volunteer_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("volunteer_organizations.id"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(String(255))
    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    volunteers_needed: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[VolunteerRequestStatus] = mapped_column(
        Enum(VolunteerRequestStatus, name="volunteer_request_status"),
        default=VolunteerRequestStatus.open,
        server_default=VolunteerRequestStatus.open.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("VolunteerOrganization", back_populates="requests")
    participants = relationship("User", secondary="volunteer_participations")


class VolunteerParticipation(Base):
    """Which user joined which volunteer request."""

    __tablename__ = "volunteer_participations"

    request_id: Mapped[int] = mapped_column(ForeignKey("volunteer_requests.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
