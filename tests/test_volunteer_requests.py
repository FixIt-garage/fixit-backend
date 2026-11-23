from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.master import Master
from app.models.user import User, UserRole
from app.models.volunteer import (
    VolunteerOrganization,
    VolunteerParticipation,
    VolunteerRequest,
    VolunteerRequestStatus,
)

PASSWORD = "TestPassword123!"
FIRST_EVENT = datetime(2026, 12, 1, 10, tzinfo=UTC)


def register(client: TestClient, email: str, role: str = "master") -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "first_name": "Test",
            "last_name": "User",
            "role": role,
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def make_volunteer(
    client: TestClient,
    factory,
    email: str = "volunteer@example.com",
    is_volunteer: bool = True,
) -> dict[str, str]:
    headers = register(client, email)
    with factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        db.add(Master(user_id=user.id, is_volunteer=is_volunteer))
        db.commit()
    return headers


def user_id(factory, email: str) -> int:
    with factory() as db:
        return db.scalar(select(User.id).where(User.email == email))


def make_organization(db) -> VolunteerOrganization:
    owner = User(
        email="org@example.com",
        password_hash="hashed-password",
        first_name="Org",
        last_name="Owner",
        role=UserRole.VOLUNTEER_ORGANIZATION,
    )
    db.add(owner)
    db.flush()
    organization = VolunteerOrganization(owner_user_id=owner.id, name="Тепла хата")
    db.add(organization)
    db.flush()
    return organization


def make_request(
    db,
    organization,
    title: str = "Help",
    city: str | None = "Львів",
    days: int | None = 1,
    needed: int | None = 5,
    status: VolunteerRequestStatus = VolunteerRequestStatus.open,
) -> VolunteerRequest:
    request = VolunteerRequest(
        organization_id=organization.id,
        title=title,
        description="Потрібні волонтери",
        city=city,
        event_date=FIRST_EVENT + timedelta(days=days) if days is not None else None,
        volunteers_needed=needed,
        status=status,
    )
    db.add(request)
    db.flush()
    return request


def seed_requests(factory, *specs: dict) -> list[int]:
    """Create one organization and a request for every spec; return the request ids."""
    with factory() as db:
        organization = make_organization(db)
        ids = [make_request(db, organization, **spec).id for spec in specs]
        db.commit()
    return ids


def add_participant(db, request, email: str, first_name: str, avatar_url: str | None = None):
    user = User(
        email=email,
        password_hash="hashed-password",
        first_name=first_name,
        last_name="User",
        avatar_url=avatar_url,
        role=UserRole.MASTER,
    )
    db.add(user)
    db.flush()
    db.add(VolunteerParticipation(request_id=request.id, user_id=user.id))
    db.flush()


@pytest.fixture
def volunteer(client: TestClient, test_session_factory) -> dict[str, str]:
    return make_volunteer(client, test_session_factory)


def test_requires_a_token(client: TestClient) -> None:
    assert client.get("/volunteer-requests").status_code == 401
    assert client.get("/volunteer-requests/1").status_code == 401


def test_only_volunteer_masters_have_access(client: TestClient, test_session_factory) -> None:
    client_headers = register(client, "client@example.com", role="client")
    plain_master = make_volunteer(client, test_session_factory, "plain@example.com", False)
    no_profile = register(client, "noprofile@example.com")

    for headers in (client_headers, plain_master, no_profile):
        assert client.get("/volunteer-requests", headers=headers).status_code == 403
        assert client.get("/volunteer-requests/1", headers=headers).status_code == 403


def test_list_shows_only_open_requests_nearest_first(
    client: TestClient, test_session_factory, volunteer: dict[str, str]
) -> None:
    seed_requests(
        test_session_factory,
        {"title": "C", "days": 3},
        {"title": "Undated", "days": None},
        {"title": "A", "days": 1},
        {"title": "Closed", "days": 0, "status": VolunteerRequestStatus.closed},
        {"title": "B", "days": 2},
    )

    body = client.get("/volunteer-requests", headers=volunteer).json()

    assert [item["title"] for item in body["items"]] == ["A", "B", "C", "Undated"]
    assert body["total"] == 4


def test_city_filter_ignores_case(
    client: TestClient, test_session_factory, volunteer: dict[str, str]
) -> None:
    seed_requests(
        test_session_factory,
        {"title": "Lviv", "city": "Львів", "days": 1},
        {"title": "Kyiv", "city": "Київ", "days": 2},
        {"title": "Nowhere", "city": None, "days": 3},
    )

    def titles(**params) -> list[str]:
        response = client.get("/volunteer-requests", params=params, headers=volunteer)
        return [item["title"] for item in response.json()["items"]]

    assert titles(city="львів") == ["Lviv"]
    assert titles(city="  КИЇВ ") == ["Kyiv"]
    assert titles(city="   ") == ["Lviv", "Kyiv", "Nowhere"]
    assert titles(city="Одеса") == []


def test_progress_shows_joined_and_needed(
    client: TestClient, test_session_factory, volunteer: dict[str, str]
) -> None:
    limited, open_ended = seed_requests(
        test_session_factory,
        {"title": "Limited", "needed": 3, "days": 1},
        {"title": "Open ended", "needed": None, "days": 2},
    )
    with test_session_factory() as db:
        request = db.get(VolunteerRequest, limited)
        add_participant(db, request, "anna@example.com", "Anna")
        add_participant(db, request, "petro@example.com", "Petro")
        db.commit()

    items = client.get("/volunteer-requests", headers=volunteer).json()["items"]

    assert (items[0]["joined"], items[0]["needed"]) == (2, 3)
    assert (items[1]["joined"], items[1]["needed"]) == (0, None)


def test_list_is_paginated(
    client: TestClient, test_session_factory, volunteer: dict[str, str]
) -> None:
    seed_requests(
        test_session_factory,
        {"title": "A", "days": 1},
        {"title": "B", "days": 2},
        {"title": "C", "days": 3},
    )

    first = client.get("/volunteer-requests", params={"limit": 2}, headers=volunteer).json()
    second = client.get(
        "/volunteer-requests", params={"limit": 2, "offset": 2}, headers=volunteer
    ).json()

    assert [item["title"] for item in first["items"]] == ["A", "B"]
    assert [item["title"] for item in second["items"]] == ["C"]
    assert first["total"] == second["total"] == 3
    assert (
        client.get("/volunteer-requests", params={"limit": 0}, headers=volunteer).status_code == 422
    )


def test_details_show_participants_without_contacts(
    client: TestClient, test_session_factory, volunteer: dict[str, str]
) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help"})
    with test_session_factory() as db:
        request = db.get(VolunteerRequest, request_id)
        add_participant(db, request, "anna@example.com", "Anna", "https://example.com/a.png")
        add_participant(db, request, "petro@example.com", "Petro")
        db.commit()

    body = client.get(f"/volunteer-requests/{request_id}", headers=volunteer).json()

    assert body["title"] == "Help"
    assert body["organization"]["name"] == "Тепла хата"
    assert body["joined"] == 2
    assert sorted(person["first_name"] for person in body["participants"]) == ["Anna", "Petro"]
    assert set(body["participants"][0]) == {"id", "first_name", "avatar_url"}
    assert body["is_joined"] is False


def test_details_tell_whether_the_current_user_joined(
    client: TestClient, test_session_factory, volunteer: dict[str, str]
) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help"})
    with test_session_factory() as db:
        db.add(
            VolunteerParticipation(
                request_id=request_id,
                user_id=user_id(test_session_factory, "volunteer@example.com"),
            )
        )
        db.commit()

    detail = client.get(f"/volunteer-requests/{request_id}", headers=volunteer).json()
    listed = client.get("/volunteer-requests", headers=volunteer).json()["items"][0]

    assert detail["is_joined"] is True
    assert listed["is_joined"] is True


def test_details_show_at_most_ten_participants(
    client: TestClient, test_session_factory, volunteer: dict[str, str]
) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help", "needed": 20})
    with test_session_factory() as db:
        request = db.get(VolunteerRequest, request_id)
        for number in range(12):
            add_participant(db, request, f"user{number}@example.com", f"User{number}")
        db.commit()

    body = client.get(f"/volunteer-requests/{request_id}", headers=volunteer).json()

    assert body["joined"] == 12
    assert len(body["participants"]) == 10


def test_closed_request_can_be_opened_and_unknown_one_is_not_found(
    client: TestClient, test_session_factory, volunteer: dict[str, str]
) -> None:
    [closed_id] = seed_requests(
        test_session_factory, {"title": "Done", "status": VolunteerRequestStatus.closed}
    )

    closed = client.get(f"/volunteer-requests/{closed_id}", headers=volunteer)
    unknown = client.get("/volunteer-requests/999999", headers=volunteer)

    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert unknown.status_code == 404
