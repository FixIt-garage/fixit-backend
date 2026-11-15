from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Company(Base):
    """Service center."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(255))
    schedule: Mapped[str | None] = mapped_column(Text)

    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    reviews_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    services = relationship(
        "Service",
        secondary="company_services",
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
