import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.user import User, UserRole
from app.models.volunteer import (
    VolunteerOrganization,
    VolunteerParticipation,
    VolunteerRequest,
)


def make_user(db, email: str, role: UserRole = UserRole.MASTER) -> User:
    user = User(
        email=email,
        password_hash="hashed-password",
        first_name="Test",
        last_name="User",
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def make_request(db, title: str = "Допомога переселенцям") -> VolunteerRequest:
    owner = make_user(db, f"org-{title}@example.com", UserRole.VOLUNTEER_ORGANIZATION)
    organization = VolunteerOrganization(owner_user_id=owner.id, name=f"Org {title}")
    db.add(organization)
    db.flush()
    request = VolunteerRequest(
        organization_id=organization.id, title=title, description="Потрібні волонтери"
    )
    db.add(request)
    db.flush()
    return request


def test_joined_at_is_filled_automatically(test_session_factory) -> None:
    with test_session_factory() as db:
        request = make_request(db)
        volunteer = make_user(db, "volunteer@example.com")
        participation = VolunteerParticipation(request_id=request.id, user_id=volunteer.id)
        db.add(participation)
        db.commit()
        db.refresh(participation)

        assert participation.joined_at is not None


def test_user_cannot_join_the_same_request_twice(test_session_factory) -> None:
    with test_session_factory() as db:
        request = make_request(db)
        volunteer = make_user(db, "volunteer@example.com")
        db.add(VolunteerParticipation(request_id=request.id, user_id=volunteer.id))
        db.commit()
        request_id, user_id = request.id, volunteer.id

    with test_session_factory() as db, pytest.raises(IntegrityError):
        db.add(VolunteerParticipation(request_id=request_id, user_id=user_id))
        db.commit()


def test_user_can_join_several_requests_and_a_request_has_several_users(
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        first = make_request(db, "First")
        second = make_request(db, "Second")
        anna = make_user(db, "anna@example.com")
        petro = make_user(db, "petro@example.com")
        db.add_all(
            [
                VolunteerParticipation(request_id=first.id, user_id=anna.id),
                VolunteerParticipation(request_id=second.id, user_id=anna.id),
                VolunteerParticipation(request_id=first.id, user_id=petro.id),
            ]
        )
        db.commit()
        first_id, anna_id = first.id, anna.id

    with test_session_factory() as db:
        joined_first = db.scalars(
            select(VolunteerParticipation.user_id).where(
                VolunteerParticipation.request_id == first_id
            )
        ).all()
        joined_by_anna = db.scalars(
            select(VolunteerParticipation.request_id).where(
                VolunteerParticipation.user_id == anna_id
            )
        ).all()

        assert len(joined_first) == 2
        assert len(joined_by_anna) == 2


def test_request_lists_its_participants(test_session_factory) -> None:
    with test_session_factory() as db:
        request = make_request(db)
        anna = make_user(db, "anna@example.com")
        petro = make_user(db, "petro@example.com")
        db.add_all(
            [
                VolunteerParticipation(request_id=request.id, user_id=anna.id),
                VolunteerParticipation(request_id=request.id, user_id=petro.id),
            ]
        )
        db.commit()
        db.refresh(request)

        assert sorted(user.email for user in request.participants) == [
            "anna@example.com",
            "petro@example.com",
        ]


def test_participation_needs_an_existing_request_and_user(test_session_factory) -> None:
    with test_session_factory() as db, pytest.raises(IntegrityError):
        db.add(VolunteerParticipation(request_id=999999, user_id=999999))
        db.commit()
