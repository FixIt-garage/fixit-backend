from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db import get_db
from app.models.upload import Upload, UploadKind
from app.models.user import User
from app.schemas.upload import UploadRead
from app.services import upload as upload_service

router = APIRouter(prefix="/uploads", tags=["Uploads"])


def upload_url(request: Request, upload: Upload) -> str:
    """Absolute URL of a stored file, e.g. http://localhost:8000/media/avatars/x.jpg."""
    return str(request.url_for("media", path=upload.path))


@router.post("", response_model=UploadRead, status_code=status.HTTP_201_CREATED)
async def create_upload(
    request: Request,
    kind: Annotated[UploadKind, Form(description="avatar or chat")],
    file: Annotated[UploadFile, File(description="jpeg, png or heic image")],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadRead:
    """Upload an avatar or a chat photo and get back its URL."""
    # Read one byte more than allowed, so a too large file is noticed without reading all of it.
    data = await file.read(upload_service.max_upload_bytes() + 1)
    try:
        upload = upload_service.create_upload(db, current_user, kind, data)
    except upload_service.FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File is larger than {upload_service.settings.max_upload_size_mb} MB",
        ) from exc
    except upload_service.UnsupportedImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only jpeg, png and heic images are allowed",
        ) from exc

    url = upload_url(request, upload)
    if kind == UploadKind.AVATAR:
        upload_service.set_avatar(db, current_user, url)

    return UploadRead(
        id=upload.id,
        kind=upload.kind,
        url=url,
        content_type=upload.content_type,
        size_bytes=upload.size_bytes,
        created_at=upload.created_at,
    )