from pydantic import BaseModel, ConfigDict


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str | None
    name_uk: str | None
    parent_id: int | None
    sort_order: int
