from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db import get_db
from app.models.upload import Upload, UploadKind
from app.models.user import User
from app.schemas.upload import UploadRead
from app.services import upload as upload_service
from app.services.storage import get_storage

router = APIRouter(prefix="/uploads", tags=["Uploads"])


def upload_url(request: Request, upload: Upload) -> str:
    """Absolute URL of a stored file.

    Avatars are public: /media/avatars/<name>. Chat photos are private and go through
    GET /uploads/{id}/file, which checks the token and the conversation.
    """
    if upload.kind == UploadKind.AVATAR:
        return str(request.url_for("avatars", path=upload.path.removeprefix("avatars/")))
    return str(request.url_for("get_upload_file", upload_id=upload.id))


# A plain "def" (not "async def"): FastAPI runs it in a worker thread, so slow image
# processing, file writes and database calls do not block other requests.
@router.post("", response_model=UploadRead, status_code=status.HTTP_201_CREATED)
def create_upload(
    request: Request,
    kind: Annotated[UploadKind, Form(description="avatar or chat")],
    file: Annotated[UploadFile, File(description="jpeg, png or heic image")],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadRead:
    """Upload an avatar or a chat photo and get back its URL."""
    # Read one byte more than allowed, so a too large file is noticed without reading all of it.
    data = file.file.read(upload_service.max_upload_bytes() + 1)
    try:
        upload = upload_service.create_upload(db, current_user, kind, data)
    except upload_service.FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File is larger than {upload_service.settings.max_upload_size_mb} MB",
        ) from exc
    except upload_service.ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Image is larger than {upload_service.settings.max_image_pixels} pixels",
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


@router.get(
    "/{upload_id}/file",
    response_class=FileResponse,
    responses={
        200: {"content": {"image/jpeg": {}, "image/png": {}}, "description": "The image"},
        404: {"description": "No such file, or the current user may not see it"},
    },
)
def get_upload_file(
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Download an uploaded file: your own, or a chat photo shared with you in a conversation."""
    upload = upload_service.get_upload(db, upload_id)
    # 404 rather than 403, so other people's upload ids cannot be discovered.
    if upload is None or not upload_service.can_view(db, upload, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return FileResponse(
        get_storage().local_path(upload.path),
        media_type=upload.content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )
