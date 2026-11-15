from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.company import Company
from app.schemas.review import ReviewListRead
from app.services import review as review_service

router = APIRouter(
    prefix="/service-centers",
    tags=["Service Centers"],
)


@router.get("/{company_id}/reviews", response_model=ReviewListRead)
def get_service_center_reviews(
    company_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """Return paginated reviews received by a service center."""
    if db.get(Company, company_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Service center not found",
        )

    return review_service.list_reviews(
        db,
        company_id=company_id,
        limit=limit,
        offset=offset,
    )