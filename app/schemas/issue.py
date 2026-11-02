from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.issue import IssueStatus


class IssueBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Назва проблеми")
    description: str = Field(..., min_length=1, description="Детальний опис")
    category: str = Field(..., min_length=1, max_length=100, description="Категорія проблеми")
    address: Optional[str] = Field(None, max_length=255, description="Адреса локації")


class IssueCreate(IssueBase):
    pass


class IssueUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[IssueStatus] = None
    address: Optional[str] = Field(None, max_length=255)


class IssueRead(IssueBase):
    id: int
    status: IssueStatus
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)