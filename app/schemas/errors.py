from typing import Any

from pydantic import Field

from app.schemas.base import BaseSchema


class ErrorDetail(BaseSchema):
    field: str | None = None
    message: str


class LegacyValidationError(BaseSchema):
    """One item of FastAPI's old 422 ``detail`` list."""

    loc: list[str | int]
    msg: str
    type: str


class ErrorResponse(BaseSchema):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    # Transitional: the old FastAPI field, kept until fixit-mobile reads code/message/details.
    detail: str | list[LegacyValidationError] | None = Field(
        default=None,
        deprecated=True,
        description="Deprecated. Old FastAPI error format; use code, message and details.",
    )


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Validation error"},
    500: {"model": ErrorResponse, "description": "Internal server error"},
}