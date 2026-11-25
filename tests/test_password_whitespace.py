"""Passwords are not stripped, unlike other request strings (review on PR #23)."""

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.models.user import User

PASSWORD = "  correct-password  "


def login(client: TestClient, password: str):
    return client.post("/auth/login", json={"email": "spaces@example.com", "password": password})


def test_existing_user_with_spaces_in_password_can_log_in(
    client: TestClient, test_session_factory
) -> None:
    # A user registered before this change: the hash was made from the exact value.
    with test_session_factory() as db:
        db.add(
            User(
                email="spaces@example.com",
                password_hash=hash_password(PASSWORD),
                first_name="Test",
                last_name="User",
            )
        )
        db.commit()

    assert login(client, PASSWORD).status_code == 200
    assert login(client, PASSWORD.strip()).status_code == 401


def test_register_keeps_password_exactly_as_typed(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "spaces@example.com",
            "password": PASSWORD,
            "first_name": "  Test  ",
            "last_name": "User",
        },
    )
    assert response.status_code == 201

    assert login(client, PASSWORD).status_code == 200
    assert login(client, PASSWORD.strip()).status_code == 401