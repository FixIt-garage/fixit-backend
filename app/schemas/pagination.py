from pydantic import Field

from app.schemas.base import BaseSchema


class PageParams(BaseSchema):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class Page[T](BaseSchema):
    items: list[T]
    total: int
    limit: int
    offset: int
