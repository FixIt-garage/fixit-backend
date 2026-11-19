from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.review import ReviewTag


class ReviewCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    rating: int = Field(..., ge=1, le=5)
    tags: list[ReviewTag] = Field(default_factory=list, max_length=5)
    comment: str | None = Field(None, max_length=2000)

    @model_validator(mode="after")
    def check_unique_tags(self):
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("Review tags must be unique")
        return self


class ReviewRead(BaseModel):
    id: int
    issue_id: int
    master_id: int | None
    company_id: int | None
    rating: int
    tags: list[ReviewTag]
    comment: str | None
    created_at: datetime
    author_first_name: str
    author_last_name: str
    author_avatar_url: str | None


class ReviewListRead(BaseModel):
    items: list[ReviewRead]
    total: int
    limit: int
    offset: int
