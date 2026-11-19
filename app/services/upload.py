import io
import uuid

import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.config import settings
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


def max_upload_bytes() -> int:
    return settings.max_upload_size_mb * 1024 * 1024


def _open_image(data: bytes) -> Image.Image:
    """Open and fully decode the image, or raise UnsupportedImageError."""
    try:
        image = Image.open(io.BytesIO(data))
        image_format = image.format
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError) as exc:
        raise UnsupportedImageError from exc
    if image_format not in ALLOWED_FORMATS:
        raise UnsupportedImageError
    # Apply the camera rotation before EXIF is dropped on re-encoding.
    return ImageOps.exif_transpose(image)


def _encode(image: Image.Image, kind: UploadKind) -> tuple[bytes, str, str]:
    """Re-encode the image. This also removes EXIF data such as the GPS location."""
    if kind == UploadKind.AVATAR:
        size = settings.avatar_size_px
        image = ImageOps.fit(image, (size, size))

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