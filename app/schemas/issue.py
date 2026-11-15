from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.issue import IssueStatus

DESCRIPTION_MAX_LENGTH = 500


class IssueCreate(BaseModel):
    # Whitespace is stripped before the length checks, so "   " is rejected.
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=255, description="Назва проблеми")
    description: str = Field(
        ...,
        min_length=1,
        max_length=DESCRIPTION_MAX_LENGTH,
        description="Детальний опис",
    )
    category_id: int = Field(..., ge=1, description="ID категорії з GET /categories")
    address: str | None = Field(None, max_length=255, description="Адреса локації")
    district: str | None = Field(None, max_length=100, description="Район")

    assignee_master_id: int | None = Field(None, ge=1, description="ID профілю майстра")
    assignee_company_id: int | None = Field(None, ge=1, description="ID сервісного центру")

    @model_validator(mode="after")
    def check_assignee(self) -> Self:
        if self.assignee_master_id is not None and self.assignee_company_id is not None:
            raise ValueError("Choose either a master or a service center")
        return self


class IssueUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, min_length=1, max_length=DESCRIPTION_MAX_LENGTH)
    category_id: int | None = Field(None, ge=1)
    address: str | None = Field(None, max_length=255)
    district: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def check_provided_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for name in ("title", "description", "category_id"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class IssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category_id: int
    address: str | None
    district: str | None
    status: IssueStatus
    owner_id: int
    assignee_master_id: int | None
    assignee_company_id: int | None
    created_at: datetime
    updated_at: datetime


class IssueStatusEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: IssueStatus
    created_at: datetime
    actor_id: int


class AssignedMasterRead(BaseModel):
    name: str
    rating: Decimal | None


class IssueDetailRead(IssueRead):
    timeline: list[IssueStatusEventRead]
    assigned_master: AssignedMasterRead | None


class IssueCountsRead(BaseModel):
    all: int
    active: int
    done: int


class IssueListRead(BaseModel):
    items: list[IssueRead]
    counts: IssueCountsRead


class MasterRequestRead(BaseModel):
    id: int
    title: str
    status: IssueStatus
    client_first_name: str
    district: str | None
    time_ago: str
    created_at: datetime
