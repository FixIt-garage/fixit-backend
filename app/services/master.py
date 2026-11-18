from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import Category
from app.models.master import Master
from app.models.user import User
from app.schemas.category import CategoryRead
from app.schemas.master import (
    MasterCompleteness,
    MasterContacts,
    MasterProfileRead,
    MasterProfileUpdate,
    MasterPublicRead,
)
from app.services.completeness import calculate_completeness

COMPLETENESS_STEPS = 5


class CategoryNotFoundError(Exception):
    """Raised when a category id of the profile does not exist."""
class MasterNotFoundError(Exception):
    """Raised when the master does not exist or the account is deactivated."""


def _to_float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _lock_user(db: Session, user: User) -> None:
    """Lock the user row first, so every write path takes locks in the same order.

    The order is always users, then masters. Without it, two concurrent PATCH requests
    (one with categories, one with city) can wait for each other and deadlock.
    """
    db.execute(select(User.id).where(User.id == user.id).with_for_update())


def _get_or_create_master(db: Session, user: User) -> Master:
    """Return the master profile; the first save creates it atomically.

    Two requests can both see no profile. INSERT ... ON CONFLICT DO NOTHING lets the
    second one skip the insert instead of failing on UNIQUE(masters.user_id), and the
    profile is read again, so both requests work with the same row.
    """
    if user.master_profile is None:
        insert_master = (
            pg_insert(Master)
            .values(user_id=user.id)
            .on_conflict_do_nothing(index_elements=["user_id"])
        )
        db.execute(insert_master)
        db.expire(user, ["master_profile"])
    return user.master_profile


def _lock_master(db: Session, master: Master) -> None:
    """Lock the master row and reload it with its current categories.

    The replacement of the category list is serialized: a concurrent request waits here
    until the first one commits, and then reads the up-to-date set instead of a stale one.
    """
    db.execute(select(Master.id).where(Master.id == master.id).with_for_update())
    db.refresh(master, ["categories"])


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

    _lock_user(db, user)
    master = _get_or_create_master(db, user)
    if categories is not None:
        _lock_master(db, master)
        master.categories = categories
    if "city" in changes:
        user.city = changes.pop("city")
    for field, value in changes.items():
        setattr(master, field, value)

    db.commit()
    db.refresh(user)
    return build_profile(user)


def set_volunteer(db: Session, user: User, is_volunteer: bool) -> MasterProfileRead:
    _lock_user(db, user)
    master = _get_or_create_master(db, user)
    master.is_volunteer = is_volunteer
    db.commit()
    db.refresh(user)
    return build_profile(user)
def get_public_profile(db: Session, master_id: int) -> MasterPublicRead:
    """Public profile of a master; only contacts that are meant to be public are included."""
    master = db.scalar(
        select(Master)
        .where(Master.id == master_id)
        .options(selectinload(Master.user), selectinload(Master.categories))
    )
    if master is None or not master.user.is_active:
        raise MasterNotFoundError(master_id)

    user = master.user
    return MasterPublicRead(
        id=master.id,
        public_id=user.public_id,
        first_name=user.first_name,
        last_name=user.last_name,
        avatar_url=user.avatar_url,
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
        contacts=MasterContacts(phone=user.phone),
    )


def get_own_profile(user: User) -> MasterProfileRead:
    """The master's own profile; empty (0 of 5) while the master has not saved anything yet."""
    completeness = calculate_completeness(user)
    master = user.master_profile
    if master is None:
        return MasterProfileRead(
            id=None,
            city=user.city,
            district=None,
            experience_years=None,
            call_out_price=None,
            schedule=None,
            is_volunteer=False,
            rating=None,
            reviews_count=0,
            categories=[],
            completeness=MasterCompleteness(
                filled=completeness.percent // 20,
                total=COMPLETENESS_STEPS,
                percent=completeness.percent,
                next_field=completeness.next_field,
            ),
        )
    return build_profile(user)