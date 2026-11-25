from app.schemas.base import BaseSchema


class CategoryRead(BaseSchema):
    id: int
    name: str
    slug: str | None
    name_uk: str | None
    parent_id: int | None
    sort_order: int
