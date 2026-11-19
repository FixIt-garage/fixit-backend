from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base for all DTOs."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


class RequestSchema(BaseSchema):
    """Base for request DTOs (XCreate, XUpdate). Rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")
