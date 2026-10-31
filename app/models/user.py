from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SQLAlchemyEnum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UserRole(str, Enum):
    CLIENT = "client"
    MASTER = "master"
    SERVICE_CENTER = "service_center"
    VOLUNTEER_ORGANIZATION = "volunteer_organization"


class User(Base):
    """One account per person. A user can also get a master profile."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(String(255))

    role: Mapped[UserRole] = mapped_column(
        SQLAlchemyEnum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=UserRole.CLIENT,
        server_default=UserRole.CLIENT.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    master_profile = relationship("Master", back_populates="user", uselist=False)
