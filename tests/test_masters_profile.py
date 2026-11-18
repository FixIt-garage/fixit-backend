import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.catalog import Category
from app.models.master import Master
from app.models.user import User
from app.schemas.master import MasterProfileUpdate
from app.services import master as master_service


@pytest.fixture
def category_ids(test_session_factory) -> list[int]:
    """Ids of two real categories created by the seed migration."""
    with test_session_factory() as db:
        values = list(db.scalars(select(Category.id).order_by(Category.id).limit(2)))
    assert len(values) == 2
    return values


def register(client: TestClient, email: str, role: str | None = None) -> dict[str, str]:
    payload = {
        "email": email,
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "User",
    }
    if role is not None:
        payload["role"] = role
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def master_headers(client: TestClient, email: str = "master@example.com") -> dict[str, str]:
    return register(client, email, role="master")


def test_first_save_creates_an_empty_profile(client: TestClient) -> None:
    headers = master_headers(client)

    response = client.patch("/masters/me", json={"district": "Sykhiv"}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["district"] == "Sykhiv"
    assert body["experience_years"] is None
    assert body["call_out_price"] is None
    assert body["schedule"] is None
    assert body["is_volunteer"] is False
    assert body["rating"] is None
    assert body["reviews_count"] == 0
    assert body["categories"] == []
    assert body["completeness"] == {
        "filled": 0,
        "total": 5,
        "percent": 0,
        "next_field": "categories",
    }


def test_partial_saves_keep_earlier_values(client: TestClient) -> None:
    headers = master_headers(client)
    client.patch("/masters/me", json={"experience_years": 7}, headers=headers)

    response = client.patch("/masters/me", json={"schedule": "Mon-Fri 9-18"}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["experience_years"] == 7
    assert body["schedule"] == "Mon-Fri 9-18"
    assert body["completeness"]["filled"] == 2


def test_complete_profile_shows_five_of_five(client: TestClient, category_ids: list[int]) -> None:
    headers = master_headers(client)

    response = client.patch(
        "/masters/me",
        json={
            "category_ids": category_ids,
            "city": "Lviv",
            "district": "Sykhiv",
            "experience_years": 7,
            "call_out_price": 300,
            "schedule": "Mon-Fri 9-18",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert [category["id"] for category in body["categories"]] == sorted(category_ids)
    assert body["call_out_price"] == 300.0
    assert body["completeness"] == {
        "filled": 5,
        "total": 5,
        "percent": 100,
        "next_field": None,
    }


def test_city_is_saved_on_the_user(client: TestClient) -> None:
    headers = master_headers(client)

    client.patch("/masters/me", json={"city": "Lviv"}, headers=headers)

    assert client.get("/users/me", headers=headers).json()["city"] == "Lviv"


def test_categories_are_replaced_and_can_be_cleared(
    client: TestClient, category_ids: list[int]
) -> None:
    headers = master_headers(client)
    client.patch("/masters/me", json={"category_ids": category_ids}, headers=headers)

    replaced = client.patch(
        "/masters/me", json={"category_ids": [category_ids[1]]}, headers=headers
    )
    cleared = client.patch("/masters/me", json={"category_ids": []}, headers=headers)

    assert [category["id"] for category in replaced.json()["categories"]] == [category_ids[1]]
    assert cleared.json()["categories"] == []


def test_null_clears_a_field(client: TestClient) -> None:
    headers = master_headers(client)
    client.patch("/masters/me", json={"experience_years": 5}, headers=headers)

    response = client.patch("/masters/me", json={"experience_years": None}, headers=headers)

    assert response.status_code == 200
    assert response.json()["experience_years"] is None


def test_unknown_category_is_rejected_and_nothing_is_saved(
    client: TestClient, test_session_factory
) -> None:
    headers = master_headers(client)

    response = client.patch(
        "/masters/me",
        json={"district": "Sykhiv", "category_ids": [999999]},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Category not found"
    with test_session_factory() as db:
        assert db.scalar(select(Master).where(Master.district == "Sykhiv")) is None


def test_client_cannot_edit_a_master_profile(client: TestClient) -> None:
    headers = register(client, "client@example.com")

    patch = client.patch("/masters/me", json={"district": "Sykhiv"}, headers=headers)
    volunteer = client.patch("/masters/me/volunteer", json={"is_volunteer": True}, headers=headers)

    assert patch.status_code == 403
    assert volunteer.status_code == 403


def test_profile_endpoints_need_a_token(client: TestClient) -> None:
    assert client.patch("/masters/me", json={"district": "x"}).status_code == 401
    assert client.patch("/masters/me/volunteer", json={"is_volunteer": True}).status_code == 401


def test_volunteer_toggle_on_and_off_keeps_other_fields(client: TestClient) -> None:
    headers = master_headers(client)
    client.patch("/masters/me", json={"experience_years": 3}, headers=headers)

    on = client.patch("/masters/me/volunteer", json={"is_volunteer": True}, headers=headers)
    off = client.patch("/masters/me/volunteer", json={"is_volunteer": False}, headers=headers)

    assert on.status_code == 200
    assert on.json()["is_volunteer"] is True
    assert off.json()["is_volunteer"] is False
    assert off.json()["experience_years"] == 3


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"district": "   "},
        {"city": ""},
        {"experience_years": -1},
        {"experience_years": 61},
        {"call_out_price": -1},
        {"schedule": ""},
        {"category_ids": [0]},
        {"is_volunteer": True},
        {"rating": 5},
    ],
)
def test_invalid_profile_body_is_rejected(client: TestClient, body: dict) -> None:
    response = client.patch("/masters/me", json=body, headers=master_headers(client))

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [{}, {"is_volunteer": "yes"}, {"is_volunteer": 1}, {"is_volunteer": None}, {"other": True}],
)
def test_invalid_volunteer_body_is_rejected(client: TestClient, body: dict) -> None:
    response = client.patch("/masters/me/volunteer", json=body, headers=master_headers(client))

    assert response.status_code == 422

def test_two_first_saves_with_separate_sessions_do_not_conflict(
    client: TestClient, test_session_factory
) -> None:
    master_headers(client)
    email = "master@example.com"

    with test_session_factory() as db_a, test_session_factory() as db_b:
        user_a = db_a.scalar(select(User).where(User.email == email))
        user_b = db_b.scalar(select(User).where(User.email == email))
        # Both sessions see "no profile yet", like two simultaneous first requests.
        assert user_a.master_profile is None
        assert user_b.master_profile is None

        master_service.update_profile(db_a, user_a, MasterProfileUpdate(district="Sykhiv"))
        master_service.set_volunteer(db_b, user_b, True)

    with test_session_factory() as db:
        masters = list(db.scalars(select(Master)))
    assert len(masters) == 1
    assert masters[0].district == "Sykhiv"
    assert masters[0].is_volunteer is True