from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.catalog import Category
from app.models.user import User
from app.models.volunteer import (
    VolunteerOrganization,
    VolunteerRequest,
    VolunteerRequestStatus,
)
from tests.test_volunteer_requests import (
    add_participant,
    make_volunteer,
    register,
)


def make_organization_user(client, factory, email: str = "org1@example.com") -> dict[str, str]:
    """A user with the organization role and its VolunteerOrganization record."""
    headers = register(client, email, role="volunteer_organization")
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == email))
        db.add(VolunteerOrganization(owner_user_id=owner.id, name=f"Org of {email}"))
        db.commit()
    return headers


def category_id(factory) -> int:
    with factory() as db:
        return db.scalar(select(Category.id).order_by(Category.id).limit(1))


def payload(factory, **overrides) -> dict:
    data = {
        "title": "Допомога переселенцям",
        "description": "Потрібні волонтери для розвантаження",
        "category_id": category_id(factory),
        "city": "Львів",
        "district": "Сихів",
        "address": "вул. Чорновола, 1",
        "event_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
        "volunteers_needed": 4,
    }
    data.update(overrides)
    return data


@pytest.fixture
def organization(client, test_session_factory) -> dict[str, str]:
    return make_organization_user(client, test_session_factory)


def request_row(factory, request_id: int) -> VolunteerRequest:
    with factory() as db:
        return db.get(VolunteerRequest, request_id)


def test_organization_creates_an_open_request(client, test_session_factory, organization) -> None:
    response = client.post(
        "/volunteer-requests", json=payload(test_session_factory), headers=organization
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Допомога переселенцям"
    assert (body["status"], body["joined"], body["needed"]) == ("open", 0, 4)
    assert body["district"] == "Сихів"
    assert body["organization"]["name"] == "Org of org1@example.com"
    assert request_row(test_session_factory, body["id"]) is not None


def test_created_request_is_visible_to_volunteers(
    client, test_session_factory, organization
) -> None:
    volunteer = make_volunteer(client, test_session_factory)
    client.post("/volunteer-requests", json=payload(test_session_factory), headers=organization)

    items = client.get("/volunteer-requests", headers=volunteer).json()["items"]

    assert [item["title"] for item in items] == ["Допомога переселенцям"]


def test_optional_fields_can_be_left_out(client, test_session_factory, organization) -> None:
    data = payload(test_session_factory)
    del data["district"], data["address"]

    response = client.post("/volunteer-requests", json=data, headers=organization)

    assert response.status_code == 201
    assert (response.json()["district"], response.json()["address"]) == (None, None)


@pytest.mark.parametrize(
    "field",
    ["title", "description", "category_id", "city", "event_date", "volunteers_needed"],
)
def test_required_fields_are_required(
    client, test_session_factory, organization, field: str
) -> None:
    data = payload(test_session_factory)
    del data[field]

    assert client.post("/volunteer-requests", json=data, headers=organization).status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "   "},
        {"description": ""},
        {"city": ""},
        {"volunteers_needed": 0},
        {"volunteers_needed": -3},
        {"category_id": 0},
        {"event_date": "2020-01-01T10:00:00+00:00"},
        {"event_date": "2099-01-01T10:00:00"},
        {"unknown_field": "x"},
    ],
)
def test_invalid_data_is_rejected(
    client, test_session_factory, organization, overrides: dict
) -> None:
    data = payload(test_session_factory, **overrides)

    assert client.post("/volunteer-requests", json=data, headers=organization).status_code == 422


def test_unknown_category_is_rejected(client, test_session_factory, organization) -> None:
    data = payload(test_session_factory, category_id=999999)

    response = client.post("/volunteer-requests", json=data, headers=organization)

    assert response.status_code == 422
    assert response.json()["detail"] == "Category not found"


def created_id(client, factory, headers, **overrides) -> int:
    response = client.post(
        "/volunteer-requests", json=payload(factory, **overrides), headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_organization_changes_only_the_sent_fields(
    client, test_session_factory, organization
) -> None:
    request_id = created_id(client, test_session_factory, organization)

    response = client.patch(
        f"/volunteer-requests/{request_id}", json={"title": "Новий заголовок"}, headers=organization
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Новий заголовок"
    assert (body["city"], body["needed"]) == ("Львів", 4)


def test_optional_fields_can_be_cleared_but_required_ones_cannot(
    client, test_session_factory, organization
) -> None:
    request_id = created_id(client, test_session_factory, organization)
    url = f"/volunteer-requests/{request_id}"

    cleared = client.patch(url, json={"district": None, "address": None}, headers=organization)
    refused = client.patch(url, json={"title": None}, headers=organization)

    assert cleared.status_code == 200
    assert (cleared.json()["district"], cleared.json()["address"]) == (None, None)
    assert refused.status_code == 422


def test_request_can_be_closed_and_opened_again(client, test_session_factory, organization) -> None:
    volunteer = make_volunteer(client, test_session_factory)
    request_id = created_id(client, test_session_factory, organization)
    url = f"/volunteer-requests/{request_id}"

    client.patch(url, json={"status": "closed"}, headers=organization)
    hidden = client.get("/volunteer-requests", headers=volunteer).json()["total"]
    client.patch(url, json={"status": "open"}, headers=organization)
    shown = client.get("/volunteer-requests", headers=volunteer).json()["total"]

    assert (hidden, shown) == (0, 1)


def test_places_cannot_drop_below_the_joined_volunteers(
    client, test_session_factory, organization
) -> None:
    request_id = created_id(client, test_session_factory, organization, volunteers_needed=5)
    with test_session_factory() as db:
        request = db.get(VolunteerRequest, request_id)
        for number in range(3):
            add_participant(db, request, f"user{number}@example.com", f"User{number}")
        db.commit()
    url = f"/volunteer-requests/{request_id}"

    too_few = client.patch(url, json={"volunteers_needed": 2}, headers=organization)
    enough = client.patch(url, json={"volunteers_needed": 3}, headers=organization)

    assert too_few.status_code == 409
    assert enough.status_code == 200
    assert enough.json()["needed"] == 3


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"volunteers_needed": None},
        {"event_date": None},
        {"volunteers_needed": 0},
        {"event_date": "2020-01-01T10:00:00+00:00"},
        {"status": "archived"},
        {"organization_id": 1},
    ],
)
def test_invalid_changes_are_rejected(
    client, test_session_factory, organization, body: dict
) -> None:
    request_id = created_id(client, test_session_factory, organization)

    response = client.patch(f"/volunteer-requests/{request_id}", json=body, headers=organization)

    assert response.status_code == 422


def test_unknown_category_in_a_change_is_rejected(
    client, test_session_factory, organization
) -> None:
    request_id = created_id(client, test_session_factory, organization)

    response = client.patch(
        f"/volunteer-requests/{request_id}", json={"category_id": 999999}, headers=organization
    )

    assert response.status_code == 422


def test_an_organization_cannot_change_a_request_of_another_one(
    client, test_session_factory, organization
) -> None:
    other = make_organization_user(client, test_session_factory, "org2@example.com")
    request_id = created_id(client, test_session_factory, organization)

    response = client.patch(
        f"/volunteer-requests/{request_id}", json={"title": "Чужий"}, headers=other
    )

    assert response.status_code == 403
    assert request_row(test_session_factory, request_id).title == "Допомога переселенцям"


def test_unknown_request_is_not_found(client, organization) -> None:
    response = client.patch("/volunteer-requests/999999", json={"title": "x"}, headers=organization)

    assert response.status_code == 404


def test_only_organizations_with_a_record_can_create_or_change(
    client, test_session_factory, organization
) -> None:
    request_id = created_id(client, test_session_factory, organization)
    data = payload(test_session_factory)
    without_record = register(client, "bare@example.com", role="volunteer_organization")
    volunteer = make_volunteer(client, test_session_factory)
    client_user = register(client, "client@example.com", role="client")

    for headers in (without_record, volunteer, client_user):
        assert client.post("/volunteer-requests", json=data, headers=headers).status_code == 403
        assert (
            client.patch(
                f"/volunteer-requests/{request_id}", json={"title": "x"}, headers=headers
            ).status_code
            == 403
        )
    assert client.post("/volunteer-requests", json=data).status_code == 401
    assert client.patch(f"/volunteer-requests/{request_id}", json={"title": "x"}).status_code == 401


def make_closed_past_request(factory, organization_email: str = "org1@example.com") -> int:
    """A closed request of the organization whose event has already happened."""
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == organization_email))
        record = db.scalar(
            select(VolunteerOrganization).where(VolunteerOrganization.owner_user_id == owner.id)
        )
        request = VolunteerRequest(
            organization_id=record.id,
            title="Минула подія",
            description="Вже відбулась",
            city="Львів",
            event_date=datetime.now(UTC) - timedelta(days=3),
            volunteers_needed=3,
            status=VolunteerRequestStatus.closed,
        )
        db.add(request)
        db.commit()
        return request.id


def test_a_closed_request_of_a_past_event_cannot_be_opened_as_it_is(
    client, test_session_factory, organization
) -> None:
    request_id = make_closed_past_request(test_session_factory)

    response = client.patch(
        f"/volunteer-requests/{request_id}", json={"status": "open"}, headers=organization
    )

    assert response.status_code == 409
    assert "new future event_date" in response.json()["detail"]
    assert request_row(test_session_factory, request_id).status == VolunteerRequestStatus.closed


def test_a_closed_request_of_a_past_event_can_be_opened_with_a_new_date(
    client, test_session_factory, organization
) -> None:
    volunteer = make_volunteer(client, test_session_factory)
    request_id = make_closed_past_request(test_session_factory)
    new_date = (datetime.now(UTC) + timedelta(days=7)).isoformat()

    response = client.patch(
        f"/volunteer-requests/{request_id}",
        json={"status": "open", "event_date": new_date},
        headers=organization,
    )
    listed = client.get("/volunteer-requests", headers=volunteer).json()

    assert response.status_code == 200
    assert response.json()["status"] == "open"
    assert [item["id"] for item in listed["items"]] == [request_id]


def test_a_closed_request_without_a_date_can_be_opened(
    client, test_session_factory, organization
) -> None:
    request_id = make_closed_past_request(test_session_factory)
    with test_session_factory() as db:
        db.get(VolunteerRequest, request_id).event_date = None
        db.commit()

    response = client.patch(
        f"/volunteer-requests/{request_id}", json={"status": "open"}, headers=organization
    )

    assert response.status_code == 200


def test_a_past_request_that_is_still_open_can_be_edited(
    client, test_session_factory, organization
) -> None:
    request_id = make_closed_past_request(test_session_factory)
    with test_session_factory() as db:
        db.get(VolunteerRequest, request_id).status = VolunteerRequestStatus.open
        db.commit()

    response = client.patch(
        f"/volunteer-requests/{request_id}", json={"title": "Виправлений"}, headers=organization
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Виправлений"
