from datetime import datetime

from app.models.upload import UploadKind
from app.schemas.base import BaseSchema


class UploadRead(BaseSchema):
    id: int
    kind: UploadKind
    url: str
    content_type: str
    size_bytes: int
    created_at: datetime