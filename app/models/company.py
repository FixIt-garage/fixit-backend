from decimal import Decimal

from sqlalchemy import (
    JSON,
    ForeignKey,
    Integer,
    Numeric,
    Sequence,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Company(Base):
    """Service center profile."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[int] = mapped_column(
        Integer,
        Sequence("companies_public_id_seq", start=1000),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str | None] = mapped_column(String(100))

    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )

    address: Mapped[str | None] = mapped_column(String(255), index=True)
    city: Mapped[str | None] = mapped_column(String(100), index=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    phone: Mapped[str | None] = mapped_column(String(32))

    schedule: Mapped[str | None] = mapped_column(Text)

    opening_hours: Mapped[dict | None] = mapped_column(JSON)

    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    reviews_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    owner = relationship("User", back_populates="service_centers")

    services = relationship(
        "Service",
        secondary="company_services",
        back_populates="companies",
    )

    categories = relationship(
        "Category",
        secondary="company_categories",
        back_populates="companies",
    )


class CompanyService(Base):
    """Many-to-many: which services a service center provides."""

    __tablename__ = "company_services"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        primary_key=True,
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id"),
        primary_key=True,
    )


class CompanyCategory(Base):
    """Many-to-many: which categories a service center provides."""

    __tablename__ = "company_categories"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
