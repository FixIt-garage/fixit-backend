from pydantic import BaseModel

from app.schemas.master import MasterPublicRead
from app.schemas.service_center import ServiceCenterRead


class MasterSearchRead(BaseModel):
    items: list[MasterPublicRead]
    total: int
    limit: int
    offset: int


class ServiceCenterSearchRead(BaseModel):
    items: list[ServiceCenterRead]
    total: int
    limit: int
    offset: int
