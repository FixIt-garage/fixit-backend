from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import Category, Service
from app.models.company import Company
from app.models.master import Master
from app.models.user import User, UserRole
from app.schemas.category import CategoryRead
from app.schemas.search import (
    MasterSearchItem,
    MasterSearchRead,
    ServiceCenterSearchRead,
)
from app.services.service_center import build_service_center_read


def _to_float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def search_masters(
    db: Session,
    city: str | None = None,
    category_id: int | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> MasterSearchRead:
    """Search active masters with sufficiently complete profiles."""

    filters = [
        User.role == UserRole.MASTER,
        User.is_active.is_(True),
        User.city.is_not(None),
        func.trim(User.city) != "",
        Master.experience_years.is_not(None),
        Master.call_out_price.is_not(None),
        Master.schedule.is_not(None),
        func.trim(Master.schedule) != "",
        Master.categories.any(),
    ]

    if city and city.strip():
        filters.append(func.lower(func.trim(User.city)) == city.strip().lower())

    if category_id is not None:
        filters.append(Master.categories.any(Category.id == category_id))

    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Master.skills_description.ilike(pattern),
                Master.categories.any(
                    or_(
                        Category.name.ilike(pattern),
                        Category.name_uk.ilike(pattern),
                        Category.slug.ilike(pattern),
                    )
                ),
                Master.services.any(Service.name.ilike(pattern)),
            )
        )

    base_query = select(Master).join(Master.user).where(*filters)

    total_query = select(func.count()).select_from(base_query.order_by(None).subquery())
    total = db.scalar(total_query) or 0

    masters = db.scalars(
        base_query.options(
            selectinload(Master.user),
            selectinload(Master.categories),
        )
        .order_by(
            Master.rating.desc().nulls_last(),
            Master.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()

    items = [
        MasterSearchItem(
            id=master.id,
            public_id=master.user.public_id,
            first_name=master.user.first_name,
            last_name=master.user.last_name,
            avatar_url=master.user.avatar_url,
            city=master.user.city,
            district=master.district,
            experience_years=master.experience_years,
            call_out_price=_to_float(master.call_out_price),
            schedule=master.schedule,
            is_volunteer=master.is_volunteer,
            rating=_to_float(master.rating),
            reviews_count=master.reviews_count,
            categories=[
                CategoryRead.model_validate(category)
                for category in sorted(
                    master.categories,
                    key=lambda category: category.id,
                )
            ],
        )
        for master in masters
    ]

    return MasterSearchRead(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


def search_service_centers(
    db: Session,
    city: str | None = None,
    category_id: int | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> ServiceCenterSearchRead:
    """Search service centers by city, category and text."""

    filters = [
        Company.type == "service_center",
    ]

    if city and city.strip():
        filters.append(func.lower(func.trim(Company.city)) == city.strip().lower())

    if category_id is not None:
        filters.append(Company.categories.any(Category.id == category_id))

    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Company.categories.any(
                    or_(
                        Category.name.ilike(pattern),
                        Category.name_uk.ilike(pattern),
                        Category.slug.ilike(pattern),
                    )
                ),
                Company.services.any(Service.name.ilike(pattern)),
            )
        )

    base_query = select(Company).where(*filters)

    total_query = select(func.count()).select_from(base_query.order_by(None).subquery())
    total = db.scalar(total_query) or 0

    companies = db.scalars(
        base_query.options(
            selectinload(Company.categories),
            selectinload(Company.services),
        )
        .order_by(
            Company.rating.desc().nulls_last(),
            Company.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()

    items = [build_service_center_read(company) for company in companies]

    return ServiceCenterSearchRead(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
