import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.user import User, UserRole
from app.models.volunteer import VolunteerOrganization


def make_owner(db, email: str = "org@example.com") -> User:
    user = User(
        email=email,
        password_hash="hashed-password",
        first_name="Test",
        last_name="Organization",
        role=UserRole.VOLUNTEER_ORGANIZATION,
    )
    db.add(user)
    db.flush()
    return user


def test_new_organization_is_not_verified(test_session_factory) -> None:
    with test_session_factory() as db:
        owner = make_owner(db)
        organization = VolunteerOrganization(owner_user_id=owner.id, name="Тепла хата")
        db.add(organization)
        db.commit()
        db.refresh(organization)

        assert organization.is_verified is False
        assert organization.owner.id == owner.id


def test_each_user_can_have_only_one_organization(test_session_factory) -> None:
    with test_session_factory() as db:
        owner = make_owner(db)
        db.add(VolunteerOrganization(owner_user_id=owner.id, name="First"))
        db.commit()
        owner_id = owner.id

    with test_session_factory() as db, pytest.raises(IntegrityError):
        db.add(VolunteerOrganization(owner_user_id=owner_id, name="Second"))
        db.commit()


def test_different_users_have_their_own_organizations(test_session_factory) -> None:
    with test_session_factory() as db:
        first = make_owner(db, "first@example.com")
        second = make_owner(db, "second@example.com")
        db.add_all(
            [
                VolunteerOrganization(owner_user_id=first.id, name="First"),
                VolunteerOrganization(owner_user_id=second.id, name="Second"),
            ]
        )
        db.commit()

        total = db.scalar(select(func.count()).select_from(VolunteerOrganization))
        assert total == 2
