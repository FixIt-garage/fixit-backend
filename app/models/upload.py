from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UploadKind(StrEnum):
    AVATAR = "avatar"
    CHAT = "chat"


UPLOAD_KIND_TYPE = SQLAlchemyEnum(
    UploadKind,
    name="upload_kind",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Upload(Base):
    """A file a user uploaded: an avatar or a photo for a chat message."""

    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    kind: Mapped[UploadKind] = mapped_column(UPLOAD_KIND_TYPE, nullable=False)
    # Path inside the storage, e.g. "avatars/3f2a....jpg". The public URL is built from it.
    path: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )