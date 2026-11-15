from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import Category, Service
from app.models.company import Company
from app.models.user import User
from app.schemas.service_center import (
    OpeningHours,
    ServiceCenterLocation,
    ServiceCenterRead,
    ServiceCenterUpdate,
)

KYIV_TZ = ZoneInfo("Europe/Kyiv")

WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


class ServiceCenterNotFoundError(Exception):
    """The service center does not exist."""


class MultipleServiceCentersError(Exception):
    """The owner has more than one service center."""


class CatalogItemsNotFoundError(Exception):
    """One or more requested categories or services do not exist."""


def get_working_status(
    opening_hours: dict | None,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Calculate whether the service center is open in the Kyiv timezone."""
    if not opening_hours:
        return False, "Графік не вказано"

    current = now or datetime.now(KYIV_TZ)

    if current.tzinfo is None:
        current = current.replace(tzinfo=KYIV_TZ)
    else:
        current = current.astimezone(KYIV_TZ)

    weekday = WEEKDAYS[current.weekday()]
    today_hours = opening_hours.get(weekday)

    if today_hours is None:
        return False, "Зачинено"

    opening_time = datetime.strptime(today_hours["open"], "%H:%M").time()
    closing_time = datetime.strptime(today_hours["close"], "%H:%M").time()

    if opening_time <= current.time() < closing_time:
        return True, f"Відчинено до {closing_time.strftime('%H:%M')}"

    return False, "Зачинено"


def build_service_center_read(
    company: Company,
    now: datetime | None = None,
) -> ServiceCenterRead:
    """Build the complete public service center response."""
    is_open, working_status = get_working_status(
        company.opening_hours,
        now,
    )

    location = None
    if company.latitude is not None and company.longitude is not None:
        location = ServiceCenterLocation(
            latitude=company.latitude,
            longitude=company.longitude,
        )

    opening_hours = (
        OpeningHours.model_validate(company.opening_hours)
        if company.opening_hours is not None
        else None
    )

    return ServiceCenterRead(
        public_id=company.public_id,
        name=company.name,
        address=company.address,
        phone=company.phone,
        location=location,
        rating=company.rating,
        reviews_count=company.reviews_count,
        opening_hours=opening_hours,
        is_open=is_open,
        working_status=working_status,
        categories=company.categories,
        services=company.services,
    )


def get_service_center(
    db: Session,
    public_id: int,
    now: datetime | None = None,
) -> ServiceCenterRead:
    """Get a service center by its public ID."""
    company = db.scalar(
        select(Company)
        .where(
            Company.public_id == public_id,
            Company.type == "service_center",
        )
        .options(
            selectinload(Company.categories),
            selectinload(Company.services),
        )
    )

    if company is None:
        raise ServiceCenterNotFoundError(public_id)

    return build_service_center_read(company, now)


def update_my_service_center(
    db: Session,
    user: User,
    data: ServiceCenterUpdate,
) -> ServiceCenterRead:
    """Update the service center owned by the current user."""
    companies = db.scalars(
        select(Company)
        .where(
            Company.owner_id == user.id,
            Company.type == "service_center",
        )
        .options(
            selectinload(Company.categories),
            selectinload(Company.services),
        )
    ).all()

    if not companies:
        raise ServiceCenterNotFoundError(user.id)

    if len(companies) > 1:
        raise MultipleServiceCentersError(user.id)

    company = companies[0]
    changes = data.model_dump(exclude_unset=True, mode="json")

    if "opening_hours" in changes:
        changes.pop("opening_hours")

        if data.opening_hours is None:
            company.opening_hours = None
        else:
            current_hours = dict(company.opening_hours or {})
            updated_hours = data.opening_hours.model_dump(
                exclude_unset=True,
                mode="json",
            )
            current_hours.update(updated_hours)
            company.opening_hours = current_hours

    category_ids = changes.pop("category_ids", None)
    service_ids = changes.pop("service_ids", None)

    if category_ids is not None:
        categories = db.scalars(select(Category).where(Category.id.in_(category_ids))).all()

        if len(categories) != len(category_ids):
            raise CatalogItemsNotFoundError("categories")

        company.categories = categories

    if service_ids is not None:
        services = db.scalars(select(Service).where(Service.id.in_(service_ids))).all()

        if len(services) != len(service_ids):
            raise CatalogItemsNotFoundError("services")

        company.services = services

    for field, value in changes.items():
        setattr(company, field, value)

    db.commit()
    db.refresh(company)

    return build_service_center_read(company)
