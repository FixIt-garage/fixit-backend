from pydantic import Field

from app.schemas.base import BaseSchema


class ErrorDetail(BaseSchema):
    field: str | None = None
    message: str


class ErrorResponse(BaseSchema):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
