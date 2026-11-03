from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.issue import IssueStatus


class IssueCreate(BaseModel):
    # Whitespace is stripped before the length checks, so "   " is rejected.
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=255, description="Назва проблеми")
    description: str = Field(..., min_length=1, description="Детальний опис")
    category_id: int = Field(..., ge=1, description="ID категорії з GET /categories")
    address: str | None = Field(None, max_length=255, description="Адреса локації")


class IssueUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, min_length=1)
    category_id: int | None = Field(None, ge=1)
    status: IssueStatus | None = None
    address: str | None = Field(None, max_length=255)


class IssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category_id: int
    address: str | None
    status: IssueStatus
    owner_id: int
    created_at: datetime
    updated_at: datetime
