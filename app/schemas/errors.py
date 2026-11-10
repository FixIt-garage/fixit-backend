from typing import Any

from pydantic import Field

from app.schemas.base import BaseSchema


class ErrorDetail(BaseSchema):
    field: str | None = None
    message: str


class ErrorResponse(BaseSchema):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Validation error"},
    500: {"model": ErrorResponse, "description": "Internal server error"},
}