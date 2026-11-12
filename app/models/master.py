from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Master(Base):
    """Master profile of a user (1:1)."""

    __tablename__ = "masters"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    skills_description: Mapped[str | None] = mapped_column(Text)
    # Cached average of the master's reviews; recalculate on every new review.
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Profile fields that the master fills in step by step (the city lives on the user).
    district: Mapped[str | None] = mapped_column(String(100))
    experience_years: Mapped[int | None] = mapped_column(Integer)
    call_out_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    schedule: Mapped[str | None] = mapped_column(String(255))
    is_volunteer: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    user = relationship("User", back_populates="master_profile")
    company = relationship("Company")
    services = relationship("Service", secondary="master_services", back_populates="masters")
    categories = relationship("Category", secondary="master_categories")


class MasterService(Base):
    """Many-to-many: which services a master provides."""

    __tablename__ = "master_services"

    master_id: Mapped[int] = mapped_column(ForeignKey("masters.id"), primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), primary_key=True)


class MasterCategory(Base):
    """Many-to-many: which repair categories a master works in."""

    __tablename__ = "master_categories"

    master_id: Mapped[int] = mapped_column(
        ForeignKey("masters.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), primary_key=True, index=True
    )