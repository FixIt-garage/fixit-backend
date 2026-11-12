from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Category, Master, MasterService, Order, OrderStatus, Review, Service, User


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


def create_issue(client: TestClient, headers: dict[str, str], category_id: int) -> dict:
    response = client.post(
        "/issues",
        json={
            "title": "Leaking tap",
            "description": "The kitchen tap has been leaking",
            "category_id": category_id,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def category_id(test_session_factory) -> int:
    with test_session_factory() as db:
        value = db.scalar(select(Category.id).order_by(Category.id))
    assert value is not None
    return value


def add_review(
    test_session_factory, client_email: str, master_email: str, category_id: int
) -> None:
    """Create a completed order of the client with the master and a review of it."""
    with test_session_factory() as db:
        client_user = db.scalar(select(User).where(User.email == client_email))
        master_user = db.scalar(select(User).where(User.email == master_email))
        master = Master(user_id=master_user.id)
        service = Service(category_id=category_id, name="Fix a tap")
        db.add_all([master, service])
        db.flush()
        db.add(MasterService(master_id=master.id, service_id=service.id))
        db.flush()
        order = Order(
            client_id=client_user.id,
            service_id=service.id,
            master_id=master.id,
            description="Fix the tap",
            address="Lviv",
            status=OrderStatus.completed,
        )
        db.add(order)
        db.flush()
        db.add(Review(order_id=order.id, rating=5))
        db.commit()


def test_profile_requires_token(client: TestClient) -> None:
    assert client.get("/users/me").status_code == 401


def test_profile_returns_fields_without_secrets(client: TestClient) -> None:
    headers = register(
        client, "me@example.com", phone="+380501234567", address="Lviv, Shevchenka 1"
    )

    response = client.get("/users/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "me@example.com"
    assert body["phone"] == "+380501234567"
    assert body["address"] == "Lviv, Shevchenka 1"
    assert body["role"] == "client"
    assert body["public_id"] >= 1000
    assert "password_hash" not in body
    assert "password" not in body


def test_new_user_has_empty_stats(client: TestClient) -> None:
    headers = register(client, "me@example.com")

    stats = client.get("/users/me", headers=headers).json()["stats"]

    assert stats == {
        "requests_count": 0,
        "reviews_count": 0,
        "member_since_year": datetime.now(UTC).year,
    }


def test_requests_count_skips_deleted_and_other_users(client: TestClient, category_id: int) -> None:
    mine = register(client, "me@example.com")
    other = register(client, "other@example.com")
    create_issue(client, mine, category_id)
    deleted = create_issue(client, mine, category_id)
    create_issue(client, other, category_id)
    client.delete(f"/issues/{deleted['id']}", headers=mine)

    stats = client.get("/users/me", headers=mine).json()["stats"]

    assert stats["requests_count"] == 1


def test_reviews_count_for_client_and_master(
    client: TestClient, test_session_factory, category_id: int
) -> None:
    client_headers = register(client, "client@example.com")
    master_headers = register(client, "master@example.com", role="master")
    outsider = register(client, "outsider@example.com")
    add_review(test_session_factory, "client@example.com", "master@example.com", category_id)

    written = client.get("/users/me", headers=client_headers).json()["stats"]["reviews_count"]
    received = client.get("/users/me", headers=master_headers).json()["stats"]["reviews_count"]
    unrelated = client.get("/users/me", headers=outsider).json()["stats"]["reviews_count"]

    assert (written, received, unrelated) == (1, 1, 0)


def test_master_without_master_profile_has_no_reviews(client: TestClient) -> None:
    headers = register(client, "master@example.com", role="master")

    stats = client.get("/users/me", headers=headers).json()["stats"]

    assert stats["reviews_count"] == 0
