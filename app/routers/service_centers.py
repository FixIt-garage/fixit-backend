from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.db import get_db
from app.models.company import Company
from app.models.user import User, UserRole
from app.schemas.review import ReviewListRead
from app.schemas.service_center import ServiceCenterRead, ServiceCenterUpdate
from app.services import review as review_service
from app.services import service_center as service_center_service

router = APIRouter(
    prefix="/service-centers",
    tags=["Service Centers"],
)

service_center_required = require_role(UserRole.SERVICE_CENTER)


@router.patch("/me", response_model=ServiceCenterRead)
def update_my_service_center(
    data: ServiceCenterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(service_center_required),
) -> ServiceCenterRead:
    """Update the authenticated owner's service center."""
    try:
        return service_center_service.update_my_service_center(
            db,
            current_user,
            data,
        )
    except service_center_service.ServiceCenterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service center not found",
        ) from exc
    except service_center_service.MultipleServiceCentersError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multiple service centers belong to this account",
        ) from exc
    except service_center_service.CatalogItemsNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"One or more requested {exc} do not exist",
        ) from exc


@router.get("/{public_id}", response_model=ServiceCenterRead)
def get_service_center(
    public_id: int,
    db: Session = Depends(get_db),
) -> ServiceCenterRead:
    """Return a public service center profile."""
    try:
        return service_center_service.get_service_center(db, public_id)
    except service_center_service.ServiceCenterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service center not found",
        ) from exc


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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service center not found",
        )

    return review_service.list_reviews(
        db,
        company_id=company_id,
        limit=limit,
        offset=offset,
    )
