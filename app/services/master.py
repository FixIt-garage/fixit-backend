from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Category
from app.models.master import Master
from app.models.user import User
from app.schemas.category import CategoryRead
from app.schemas.master import MasterCompleteness, MasterProfileRead, MasterProfileUpdate
from app.services.completeness import calculate_completeness

COMPLETENESS_STEPS = 5


class CategoryNotFoundError(Exception):
    """Raised when a category id of the profile does not exist."""


def _to_float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _get_or_create_master(db: Session, user: User) -> Master:
    if user.master_profile is None:
        db.add(Master(user=user))
        db.flush()
    return user.master_profile


def build_profile(user: User) -> MasterProfileRead:
    """The master's own profile with the "N of 5" completeness."""
    master = user.master_profile
    completeness = calculate_completeness(user)
    return MasterProfileRead(
        id=master.id,
        city=user.city,
        district=master.district,
        experience_years=master.experience_years,
        call_out_price=_to_float(master.call_out_price),
        schedule=master.schedule,
        is_volunteer=master.is_volunteer,
        rating=_to_float(master.rating),
        reviews_count=master.reviews_count,
        categories=[
            CategoryRead.model_validate(category)
            for category in sorted(master.categories, key=lambda category: category.id)
        ],
        completeness=MasterCompleteness(
            filled=completeness.percent // 20,
            total=COMPLETENESS_STEPS,
            percent=completeness.percent,
            next_field=completeness.next_field,
        ),
    )


def update_profile(db: Session, user: User, data: MasterProfileUpdate) -> MasterProfileRead:
    """Save only the fields that were sent; the first save creates the profile."""
    changes = data.model_dump(exclude_unset=True)

    categories = None
    if "category_ids" in changes:
        ids = set(changes.pop("category_ids") or [])
        categories = list(db.scalars(select(Category).where(Category.id.in_(ids)))) if ids else []
        if len(categories) != len(ids):
            raise CategoryNotFoundError(sorted(ids))

    master = _get_or_create_master(db, user)
    if categories is not None:
        master.categories = categories
    if "city" in changes:
        user.city = changes.pop("city")
    for field, value in changes.items():
        setattr(master, field, value)

    db.commit()
    db.refresh(user)
    return build_profile(user)


def set_volunteer(db: Session, user: User, is_volunteer: bool) -> MasterProfileRead:
    master = _get_or_create_master(db, user)
    master.is_volunteer = is_volunteer
    db.commit()
    db.refresh(user)
    return build_profile(user)