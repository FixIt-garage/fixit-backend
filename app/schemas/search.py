from pydantic import BaseModel

from app.schemas.category import CategoryRead
from app.schemas.service_center import ServiceCenterRead


class MasterSearchItem(BaseModel):
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


class MasterSearchRead(BaseModel):
    items: list[MasterSearchItem]
    total: int
    limit: int
    offset: int


class ServiceCenterSearchRead(BaseModel):
    items: list[ServiceCenterRead]
    total: int
    limit: int
    offset: int
