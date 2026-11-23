from datetime import datetime

from pydantic import BaseModel

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
