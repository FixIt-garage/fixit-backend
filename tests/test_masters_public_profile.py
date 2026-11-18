from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.catalog import Category
from app.models.master import Master


@pytest.fixture
def category_ids(test_session_factory) -> list[int]:
    with test_session_factory() as db:
        values = list(db.scalars(select(Category.id).order_by(Category.id).limit(2)))
    assert len(values) == 2
    return values


def register(client: TestClient, email: str, role: str | None = None, **extra) -> dict[str, str]:
    payload = {
        "email": email,
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "User",
        **extra,
    }
    if role is not None:
        payload["role"] = role
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def master_headers(client: TestClient, email: str = "master@example.com", **extra):
    return register(client, email, role="master", **extra)


def create_empty_master(client: TestClient, headers: dict[str, str]) -> int:
    response = client.patch("/masters/me/volunteer", json={"is_volunteer": False}, headers=headers)
    assert response.status_code == 200
    return response.json()["id"]


def test_public_profile_shows_the_filled_profile(
    client: TestClient, test_session_factory, category_ids: list[int]
) -> None:
    master = master_headers(client, phone="+380501234567")
    client.patch("/users/me", json={"avatar_url": "https://example.com/a.png"}, headers=master)
    saved = client.patch(
        "/masters/me",
        json={
            "category_ids": category_ids,
            "city": "Lviv",
            "district": "Sykhiv",
            "experience_years": 7,
            "call_out_price": 300,
            "schedule": "Mon-Fri 9-18",
        },
        headers=master,
    )
    master_id = saved.json()["id"]
    client.patch("/masters/me/volunteer", json={"is_volunteer": True}, headers=master)
    with test_session_factory() as db:
        row = db.get(Master, master_id)
        row.rating = Decimal("4.50")
        row.reviews_count = 3
        db.commit()
    viewer = register(client, "client@example.com")

    response = client.get(f"/masters/{master_id}", headers=viewer)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == master_id
    assert isinstance(body["public_id"], int)
    assert (body["first_name"], body["last_name"]) == ("Test", "User")
    assert body["avatar_url"] == "https://example.com/a.png"
    assert body["city"] == "Lviv"
    assert body["district"] == "Sykhiv"
    assert body["experience_years"] == 7
    assert body["call_out_price"] == 300.0
    assert body["schedule"] == "Mon-Fri 9-18"
    assert body["is_volunteer"] is True
    assert body["rating"] == 4.5
    assert body["reviews_count"] == 3
    assert [category["id"] for category in body["categories"]] == sorted(category_ids)
    assert body["contacts"] == {"phone": "+380501234567"}


def test_public_profile_does_not_expose_private_data(client: TestClient) -> None:
    master = master_headers(client, phone="+380501234567")
    master_id = create_empty_master(client, master)
    viewer = register(client, "client@example.com")

    response = client.get(f"/masters/{master_id}", headers=viewer)

    body = response.json()
    for private_field in ("email", "password_hash", "role", "is_active", "address"):
        assert private_field not in body
        assert private_field not in body["contacts"]
    assert "master@example.com" not in response.text


def test_empty_profile_returns_nulls_not_an_error(client: TestClient) -> None:
    master = master_headers(client)
    master_id = create_empty_master(client, master)

    response = client.get(f"/masters/{master_id}", headers=master)

    assert response.status_code == 200
    body = response.json()
    assert body["city"] is None
    assert body["district"] is None
    assert body["experience_years"] is None
    assert body["call_out_price"] is None
    assert body["schedule"] is None
    assert body["rating"] is None
    assert body["reviews_count"] == 0
    assert body["is_volunteer"] is False
    assert body["categories"] == []
    assert body["contacts"] == {"phone": None}


def test_unknown_master_returns_404(client: TestClient) -> None:
    viewer = register(client, "client@example.com")

    response = client.get("/masters/999999", headers=viewer)

    assert response.status_code == 404
    assert response.json()["detail"] == "Master not found"


def test_deactivated_master_returns_404(client: TestClient, test_session_factory) -> None:
    master = master_headers(client)
    master_id = create_empty_master(client, master)
    viewer = register(client, "client@example.com")
    with test_session_factory() as db:
        db.get(Master, master_id).user.is_active = False
        db.commit()

    assert client.get(f"/masters/{master_id}", headers=viewer).status_code == 404


def test_public_profile_needs_a_token(client: TestClient) -> None:
    assert client.get("/masters/1").status_code == 401


def test_any_logged_in_role_can_open_the_profile(client: TestClient) -> None:
    master = master_headers(client)
    master_id = create_empty_master(client, master)
    other_master = master_headers(client, "other@example.com")

    assert client.get(f"/masters/{master_id}", headers=master).status_code == 200
    assert client.get(f"/masters/{master_id}", headers=other_master).status_code == 200


def test_non_numeric_master_id_is_rejected(client: TestClient) -> None:
    viewer = register(client, "client@example.com")

    assert client.get("/masters/abc", headers=viewer).status_code == 422


def test_me_routes_are_not_captured_by_the_public_profile(client: TestClient) -> None:
    master = master_headers(client)
    client_headers = register(client, "client@example.com")

    assert client.get("/masters/me/requests", headers=master).status_code == 200
    assert client.get("/masters/me/requests", headers=client_headers).status_code == 403