from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.catalog import Category
from app.models.master import Master
from app.models.user import User


def register(client: TestClient, email: str, role: str = "client", **extra) -> dict[str, str]:
    payload = {
        "email": email,
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "User",
        "role": role,
        **extra,
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def completeness(client: TestClient, headers: dict[str, str]) -> dict:
    return client.get("/users/me", headers=headers).json()["completeness"]


def add_master(test_session_factory, email: str, with_category: bool = False, **fields) -> None:
    with test_session_factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        master = Master(user_id=user.id, **fields)
        if with_category:
            master.categories = [db.scalar(select(Category).order_by(Category.id).limit(1))]
        db.add(master)
        db.commit()


def test_client_without_profile_data(client: TestClient) -> None:
    headers = register(client, "me@example.com")

    assert completeness(client, headers) == {"percent": 0, "next_field": "avatar_url"}


def test_fields_given_at_registration_count(client: TestClient) -> None:
    headers = register(client, "me@example.com", phone="+380501234567", address="Lviv")

    assert completeness(client, headers) == {"percent": 50, "next_field": "avatar_url"}


def test_client_completeness_grows_with_each_field(client: TestClient) -> None:
    headers = register(client, "me@example.com")
    steps = [
        ("avatar_url", "https://example.com/a.png", 25, "phone"),
        ("phone", "+380501234567", 50, "address"),
        ("address", "Lviv, Sykhiv", 75, "city"),
        ("city", "Lviv", 100, None),
    ]

    for field, value, percent, next_field in steps:
        response = client.patch("/users/me", json={field: value}, headers=headers)

        assert response.status_code == 200
        expected = {"percent": percent, "next_field": next_field}
        assert response.json()["completeness"] == expected
        assert completeness(client, headers) == expected


def test_clearing_a_field_lowers_the_percent(client: TestClient) -> None:
    headers = register(client, "me@example.com", phone="+380501234567")

    response = client.patch("/users/me", json={"phone": None}, headers=headers)

    assert response.json()["completeness"] == {"percent": 0, "next_field": "avatar_url"}


def test_master_without_master_profile_starts_at_zero(client: TestClient) -> None:
    headers = register(client, "master@example.com", role="master")

    assert completeness(client, headers) == {"percent": 0, "next_field": "categories"}


def test_master_city_counts_even_without_master_profile(client: TestClient) -> None:
    headers = register(client, "master@example.com", role="master")

    response = client.patch("/users/me", json={"city": "Lviv"}, headers=headers)

    assert response.json()["completeness"] == {"percent": 20, "next_field": "categories"}


def test_master_partial_profile(client: TestClient, test_session_factory) -> None:
    headers = register(client, "master@example.com", role="master")
    client.patch("/users/me", json={"city": "Lviv"}, headers=headers)
    add_master(test_session_factory, "master@example.com", experience_years=3)

    assert completeness(client, headers) == {"percent": 40, "next_field": "categories"}


def test_blank_schedule_is_not_filled(client: TestClient, test_session_factory) -> None:
    headers = register(client, "master@example.com", role="master")
    add_master(test_session_factory, "master@example.com", schedule="   ")

    assert completeness(client, headers) == {"percent": 0, "next_field": "categories"}


def test_master_with_everything_filled_is_complete(
    client: TestClient, test_session_factory
) -> None:
    headers = register(client, "master@example.com", role="master")
    client.patch("/users/me", json={"city": "Lviv"}, headers=headers)
    add_master(
        test_session_factory,
        "master@example.com",
        with_category=True,
        experience_years=5,
        call_out_price=Decimal("300"),
        schedule="Mon-Sat 9:00-19:00",
    )

    assert completeness(client, headers) == {"percent": 100, "next_field": None}


def test_other_roles_use_the_client_fields(client: TestClient) -> None:
    headers = register(client, "org@example.com", role="volunteer_organization")

    assert completeness(client, headers) == {"percent": 0, "next_field": "avatar_url"}
