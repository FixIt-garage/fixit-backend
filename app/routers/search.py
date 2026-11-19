from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.search import (
    MasterSearchRead,
    ServiceCenterSearchRead,
)
from app.services.search import (
    search_masters,
    search_service_centers,
)

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/masters", response_model=MasterSearchRead)
def get_masters_search(
    city: str | None = Query(default=None, max_length=100),
    category_id: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None, max_length=255),
    sort: Literal["rating"] = "rating",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return search_masters(
        db=db,
        city=city,
        category_id=category_id,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/service-centers", response_model=ServiceCenterSearchRead)
def get_service_centers_search(
    city: str | None = Query(default=None, max_length=100),
    category_id: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None, max_length=255),
    sort: Literal["rating"] = "rating",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return search_service_centers(
        db=db,
        city=city,
        category_id=category_id,
        q=q,
        limit=limit,
        offset=offset,
    )
