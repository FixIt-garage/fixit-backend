from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.schemas.category import CategoryRead

CategoryId = Annotated[int, Field(ge=1)]


class MasterProfileUpdate(BaseModel):
    """Partial save of the own master profile. A field sent as null is cleared."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category_ids: list[CategoryId] | None = Field(None, max_length=50)
    city: str | None = Field(None, min_length=1, max_length=100)
    district: str | None = Field(None, min_length=1, max_length=100)
    experience_years: int | None = Field(None, ge=0, le=60)
    call_out_price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    schedule: str | None = Field(None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def check_provided_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class MasterVolunteerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_volunteer: StrictBool


class MasterCompleteness(BaseModel):
    filled: int
    total: int
    percent: int
    next_field: str | None


class MasterProfileRead(BaseModel):
    id: int
    city: str | None
    district: str | None
    experience_years: int | None
    call_out_price: float | None
    schedule: str | None
    is_volunteer: bool
    rating: float | None
    reviews_count: int
    categories: list[CategoryRead]
    completeness: MasterCompleteness
class MasterContacts(BaseModel):
    phone: str | None


class MasterPublicRead(BaseModel):
    """Public master profile. The fields are listed explicitly, so private data cannot leak."""

    id: int
    public_id: int
    first_name: str
    last_name: str
    avatar_url: str | None
    city: str | None
    district: str | None
    experience_years: int | None
    call_out_price: float | None
    schedule: str | None
    is_volunteer: bool
    rating: float | None
    reviews_count: int
    categories: list[CategoryRead]
    contacts: MasterContacts