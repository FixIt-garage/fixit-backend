import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, ForeignKeyConstraint, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class OrderStatus(enum.StrEnum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class Order(Base):
    """A client's request. Master, price and date are filled in later."""

    __tablename__ = "orders"
    __table_args__ = (
        # A master can only be assigned to a service they provide.
        # Not checked while master_id is NULL (request without a master yet).
        ForeignKeyConstraint(
            ["master_id", "service_id"],
            ["master_services.master_id", "master_services.service_id"],
            name="fk_orders_master_provides_service",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    description: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(String(255))
    master_id: Mapped[int | None] = mapped_column(ForeignKey("masters.id"))
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"),
        default=OrderStatus.pending,
        server_default=OrderStatus.pending.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client = relationship("User")
    master = relationship("Master", foreign_keys=[master_id])
    service = relationship("Service")
