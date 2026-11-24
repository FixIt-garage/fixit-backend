from datetime import UTC, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.volunteer import VolunteerRequestStatus


class VolunteerOrganizationRead(BaseModel):
    id: int
    name: str
    is_verified: bool


class VolunteerParticipantRead(BaseModel):
    id: int
    first_name: str
    avatar_url: str | None


class VolunteerRequestRead(BaseModel):
    id: int
    title: str
    description: str
    category_id: int | None
    address: str | None
    city: str | None
    district: str | None
    event_date: datetime | None
    status: VolunteerRequestStatus
    joined: int
    needed: int | None
    is_joined: bool
    organization: VolunteerOrganizationRead


class VolunteerRequestDetailRead(VolunteerRequestRead):
    participants: list[VolunteerParticipantRead]


class VolunteerRequestListRead(BaseModel):
    items: list[VolunteerRequestRead]
    total: int
    limit: int
    offset: int


def _in_the_future(value: datetime | None) -> datetime | None:
    if value is not None:
        if value.tzinfo is None:
            raise ValueError("The date must have a time zone")
        if value <= datetime.now(UTC):
            raise ValueError("The event date must be in the future")
    return value


class VolunteerRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=2000)
    category_id: int = Field(ge=1)
    city: str = Field(min_length=1, max_length=100)
    district: str | None = Field(None, min_length=1, max_length=100)
    address: str | None = Field(None, min_length=1, max_length=255)
    event_date: datetime
    volunteers_needed: int = Field(ge=1, le=10000)

    _event_in_the_future = field_validator("event_date")(_in_the_future)


class VolunteerRequestUpdate(BaseModel):
    """Partial update; every field is optional, but sent fields cannot be null (except two)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, min_length=1, max_length=2000)
    category_id: int | None = Field(None, ge=1)
    city: str | None = Field(None, min_length=1, max_length=100)
    district: str | None = Field(None, min_length=1, max_length=100)
    address: str | None = Field(None, min_length=1, max_length=255)
    event_date: datetime | None = None
    volunteers_needed: int | None = Field(None, ge=1, le=10000)
    status: VolunteerRequestStatus | None = None

    _event_in_the_future = field_validator("event_date")(_in_the_future)

    @model_validator(mode="after")
    def check_provided_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        clearable = {"district", "address"}
        for name in self.model_fields_set - clearable:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self
