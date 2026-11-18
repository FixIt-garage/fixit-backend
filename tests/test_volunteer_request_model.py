import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.models.catalog import Category
from app.models.user import User, UserRole
from app.models.volunteer import VolunteerOrganization, VolunteerRequest


def make_organization(db) -> VolunteerOrganization:
    owner = User(
        email="org@example.com",
        password_hash="hashed-password",
        first_name="Test",
        last_name="Organization",
        role=UserRole.VOLUNTEER_ORGANIZATION,
    )
    db.add(owner)
    db.flush()
    organization = VolunteerOrganization(owner_user_id=owner.id, name="Тепла хата")
    db.add(organization)
    db.flush()
    return organization


def test_request_keeps_category_and_city(test_session_factory) -> None:
    with test_session_factory() as db:
        organization = make_organization(db)
        category = db.scalar(select(Category).order_by(Category.id).limit(1))
        request = VolunteerRequest(
            organization_id=organization.id,
            title="Допомога переселенцям",
            description="Потрібні волонтери",
            category_id=category.id,
            city="Львів",
        )
        db.add(request)
        db.commit()
        db.refresh(request)

        assert request.category.id == category.id
        assert request.city == "Львів"
        assert request.status.value == "open"


def test_category_and_city_are_optional(test_session_factory) -> None:
    with test_session_factory() as db:
        organization = make_organization(db)
        request = VolunteerRequest(
            organization_id=organization.id, title="Help", description="Needed"
        )
        db.add(request)
        db.commit()
        db.refresh(request)

        assert request.category_id is None
        assert request.city is None


def test_category_used_by_a_request_cannot_be_deleted(test_session_factory) -> None:
    with test_session_factory() as db:
        organization = make_organization(db)
        category = Category(name="Test category")
        db.add(category)
        db.flush()
        db.add(
            VolunteerRequest(
                organization_id=organization.id,
                title="Help",
                description="Needed",
                category_id=category.id,
            )
        )
        db.commit()
        category_id = category.id

    with test_session_factory() as db, pytest.raises(IntegrityError):
        db.execute(delete(Category).where(Category.id == category_id))
        db.commit()
