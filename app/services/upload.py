import io
import uuid

import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.chat import Conversation, Message
from app.models.upload import Upload, UploadKind
from app.models.user import User
from app.services.storage import get_storage

pillow_heif.register_heif_opener()

# Formats as Pillow reports them after reading the file itself (not its name).
ALLOWED_FORMATS = {"JPEG", "PNG", "HEIF"}


class UnsupportedImageError(Exception):
    """The file is not a jpeg, png or heic image."""


class FileTooLargeError(Exception):
    """The file is bigger than MAX_UPLOAD_SIZE_MB."""


class ImageTooLargeError(Exception):
    """The image has more pixels than MAX_IMAGE_PIXELS."""


def max_upload_bytes() -> int:
    return settings.max_upload_size_mb * 1024 * 1024


def _open_image(data: bytes) -> Image.Image:
    """Check the image and decode it, or raise UnsupportedImageError / ImageTooLargeError."""
    try:
        # Image.open only reads the header: format and size are known before decoding.
        image = Image.open(io.BytesIO(data))
    except Image.DecompressionBombError as exc:
        raise ImageTooLargeError from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise UnsupportedImageError from exc

    image_format = image.format
    if image_format not in ALLOWED_FORMATS:
        raise UnsupportedImageError
    # A small file can still hold a huge image; check it before decoding the pixels.
    width, height = image.size
    if width * height > settings.max_image_pixels:
        raise ImageTooLargeError

    try:
        image.load()
    except (OSError, ValueError) as exc:
        raise UnsupportedImageError from exc
    # Apply the camera rotation before EXIF is dropped on re-encoding.
    return ImageOps.exif_transpose(image)


def _encode(image: Image.Image, kind: UploadKind) -> tuple[bytes, str, str]:
    """Re-encode the image. This also removes EXIF data such as the GPS location."""
    if kind == UploadKind.AVATAR:
        size = settings.avatar_size_px
        image = ImageOps.fit(image, (size, size))

    # Drop every metadata block the source carried (EXIF, ICC profile, text chunks).
    # PNG would otherwise copy the ICC profile from image.info into the new file.
    image.info.clear()

    output = io.BytesIO()
    if image.mode in ("RGBA", "LA", "P"):
        image.save(output, format="PNG", optimize=True)
        return output.getvalue(), "image/png", "png"

    image.convert("RGB").save(output, format="JPEG", quality=85, optimize=True)
    return output.getvalue(), "image/jpeg", "jpg"


def create_upload(db: Session, owner: User, kind: UploadKind, data: bytes) -> Upload:
    """Validate, process and store an image, then record it in the database."""
    if len(data) > max_upload_bytes():
        raise FileTooLargeError

    image = _open_image(data)
    content, content_type, extension = _encode(image, kind)
    folder = "avatars" if kind == UploadKind.AVATAR else "chat"
    path = f"{folder}/{uuid.uuid4().hex}.{extension}"

    storage = get_storage()
    storage.save(path, content)

    upload = Upload(
        owner_id=owner.id,
        kind=kind,
        path=path,
        content_type=content_type,
        size_bytes=len(content),
    )
    db.add(upload)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(path)
        raise
    db.refresh(upload)
    return upload


def set_avatar(db: Session, user: User, url: str) -> None:
    """Point the user's profile at the new avatar."""
    user.avatar_url = url
    db.commit()


def get_upload(db: Session, upload_id: int) -> Upload | None:
    return db.get(Upload, upload_id)


def can_view(db: Session, upload: Upload, user: User) -> bool:
    """Who may download a stored file.

    Avatars are public anyway. A chat photo is visible to its owner and to the participants
    of a conversation where the owner sent it. The message must come from the owner, so
    pasting someone else's photo URL into your own chat does not give you access to it.
    """
    if upload.owner_id == user.id:
        return True
    if upload.kind != UploadKind.CHAT:
        return False

    shared_with_user = (
        select(Message.id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Message.sender_id == upload.owner_id,
            Message.photo_url.like(f"%/uploads/{upload.id}/file"),
            or_(Conversation.client_id == user.id, Conversation.master_user_id == user.id),
        )
        .limit(1)
    )
    return db.scalar(shared_with_user) is not None
