from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.models.user import UserRole
from app.schemas.validators import Address, Phone


class UserStats(BaseModel):
    requests_count: int
    reviews_count: int
    member_since_year: int


class UserProfileResponse(BaseModel):
    id: int
    public_id: int
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None
    address: str | None
    city: str | None
    avatar_url: str | None
    role: UserRole
    stats: UserStats


AvatarUrl = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=500, pattern=r"^https?://\S+$")
]


class UserUpdate(BaseModel):
    """Partial update of the own profile. Email, role and public id cannot be changed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    phone: Phone | None = None
    address: Address | None = None
    city: str | None = Field(None, min_length=1, max_length=100)
    avatar_url: AvatarUrl | None = None

    @model_validator(mode="after")
    def check_provided_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for name in ("first_name", "last_name"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self
