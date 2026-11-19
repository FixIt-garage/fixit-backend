from app.schemas.base import BaseSchema


class RootResponse(BaseSchema):
    name: str


class HealthResponse(BaseSchema):
    status: str
    database: str