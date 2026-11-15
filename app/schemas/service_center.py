from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.category import CategoryRead
from app.schemas.validators import Address, Phone

TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class OpeningInterval(BaseModel):
    """Opening and closing time for one weekday."""

    model_config = ConfigDict(extra="forbid")

    open: str = Field(pattern=TIME_PATTERN)
    close: str = Field(pattern=TIME_PATTERN)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if self.open >= self.close:
            raise ValueError("Closing time must be later than opening time")

        return self


class OpeningHours(BaseModel):
    """Service center opening hours for each weekday."""

    model_config = ConfigDict(extra="forbid")

    monday: OpeningInterval | None = None
    tuesday: OpeningInterval | None = None
    wednesday: OpeningInterval | None = None
    thursday: OpeningInterval | None = None
    friday: OpeningInterval | None = None
    saturday: OpeningInterval | None = None
    sunday: OpeningInterval | None = None


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category_id: int


class ServiceCenterLocation(BaseModel):
    latitude: float
    longitude: float


class ServiceCenterRead(BaseModel):
    """Full public service center profile."""

    public_id: int
    name: str
    address: str | None
    phone: str | None

    location: ServiceCenterLocation | None

    rating: float | None
    reviews_count: int

    opening_hours: OpeningHours | None
    is_open: bool
    working_status: str

    categories: list[CategoryRead]
    services: list[ServiceRead]


class ServiceCenterUpdate(BaseModel):
    """Fields that a service center owner can update."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str | None = Field(None, min_length=1, max_length=255)
    address: Address | None = None
    phone: Phone | None = None

    latitude: Decimal | None = Field(None, ge=-90, le=90)
    longitude: Decimal | None = Field(None, ge=-180, le=180)

    opening_hours: OpeningHours | None = None

    category_ids: list[int] = Field(default_factory=list, max_length=50)
    service_ids: list[int] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def check_provided_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")

        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")

        for field_name in ("category_ids", "service_ids"):
            values = getattr(self, field_name)
            if values is not None and len(values) != len(set(values)):
                raise ValueError(f"{field_name} must contain unique IDs")

        return self
