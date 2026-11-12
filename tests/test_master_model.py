import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.models.catalog import Category
from app.models.master import Master
from app.models.user import User, UserRole


def make_master(db) -> Master:
    user = User(
        email="master@example.com",
        password_hash="hashed-password",
        first_name="Test",
        last_name="Master",
        role=UserRole.MASTER,
    )
    db.add(user)
    db.flush()
    master = Master(user_id=user.id)
    db.add(master)
    db.commit()
    db.refresh(master)
    return master


def test_new_master_has_empty_profile_and_is_not_volunteer(test_session_factory) -> None:
    with test_session_factory() as db:
        master = make_master(db)

        assert master.district is None
        assert master.experience_years is None
        assert master.call_out_price is None
        assert master.schedule is None
        assert master.is_volunteer is False
        assert master.categories == []


def test_master_can_have_several_categories(test_session_factory) -> None:
    with test_session_factory() as db:
        master = make_master(db)
        categories = list(db.scalars(select(Category).order_by(Category.id).limit(2)))
        assert len(categories) == 2
        master.categories = categories
        db.commit()
        master_id = master.id
        expected = sorted(category.id for category in categories)

    with test_session_factory() as db:
        saved = db.get(Master, master_id)
        assert saved is not None
        assert sorted(category.id for category in saved.categories) == expected


def test_category_linked_to_master_cannot_be_deleted(test_session_factory) -> None:
    with test_session_factory() as db:
        master = make_master(db)
        category = Category(name="Test category")
        master.categories = [category]
        db.commit()
        category_id = category.id

    with test_session_factory() as db, pytest.raises(IntegrityError):
        db.execute(delete(Category).where(Category.id == category_id))
        db.commit()