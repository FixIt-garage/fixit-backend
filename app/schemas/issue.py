from datetime import datetime
from typing import Self

from pydantic import Field, model_validator

from app.models.issue import IssueStatus
from app.schemas.base import BaseSchema, RequestSchema

DESCRIPTION_MAX_LENGTH = 500


class IssueCreate(RequestSchema):
    # Whitespace is stripped before the length checks, so "   " is rejected.
    title: str = Field(..., min_length=1, max_length=255, description="Назва проблеми")
    description: str = Field(
        ...,
        min_length=1,
        max_length=DESCRIPTION_MAX_LENGTH,
        description="Детальний опис",
    )
    category_id: int = Field(..., ge=1, description="ID категорії з GET /categories")
    address: str | None = Field(None, max_length=255, description="Адреса локації")


class IssueUpdate(RequestSchema):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, min_length=1, max_length=DESCRIPTION_MAX_LENGTH)
    category_id: int | None = Field(None, ge=1)
    status: IssueStatus | None = None
    address: str | None = Field(None, max_length=255)

    @model_validator(mode="after")
    def check_provided_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for name in ("title", "description", "category_id", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class IssueRead(BaseSchema):
    id: int
    title: str
    description: str
    category_id: int
    address: str | None
    status: IssueStatus
    owner_id: int
    created_at: datetime
    updated_at: datetime
