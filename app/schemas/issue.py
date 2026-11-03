from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.issue import IssueStatus


class IssueBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Назва проблеми")
    description: str = Field(..., min_length=1, description="Детальний опис")
    category: str = Field(..., min_length=1, max_length=100, description="Категорія проблеми")
    address: str | None = Field(None, max_length=255, description="Адреса локації")


class IssueCreate(IssueBase):
    model_config = ConfigDict(str_strip_whitespace=True)


class IssueUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, min_length=1, max_length=255)
    ...


class IssueRead(IssueBase):
    id: int
    status: IssueStatus
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)