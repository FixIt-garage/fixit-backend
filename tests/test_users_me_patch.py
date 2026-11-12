import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import User


def register(client: TestClient, email: str, **extra) -> dict[str, str]:
    payload = {
        "email": email,
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "User",
        **extra,
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def get_user(test_session_factory, email: str) -> User:
    with test_session_factory() as db:
        user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def test_patch_requires_token(client: TestClient) -> None:
    assert client.patch("/users/me", json={"city": "Lviv"}).status_code == 401


def test_patch_updates_only_sent_fields(client: TestClient) -> None:
    headers = register(client, "me@example.com", phone="+380501234567", address="Kyiv")

    response = client.patch("/users/me", json={"city": "Lviv"}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["city"] == "Lviv"
    assert body["phone"] == "+380501234567"
    assert body["address"] == "Kyiv"
    assert body["first_name"] == "Test"


def test_patch_updates_all_fields(client: TestClient, test_session_factory) -> None:
    headers = register(client, "me@example.com")

    response = client.patch(
        "/users/me",
        json={
            "first_name": "Ira",
            "last_name": "Boiko",
            "phone": "+380 (67) 111-22-33",
            "address": "Lviv, Sykhiv",
            "city": "Lviv",
            "avatar_url": "https://example.com/a.png",
        },
        headers=headers,
    )

    assert response.status_code == 200
    user = get_user(test_session_factory, "me@example.com")
    assert (user.first_name, user.last_name) == ("Ira", "Boiko")
    assert user.phone == "+380671112233"
    assert (user.address, user.city) == ("Lviv, Sykhiv", "Lviv")
    assert user.avatar_url == "https://example.com/a.png"


def test_patch_returns_profile_with_stats(client: TestClient) -> None:
    headers = register(client, "me@example.com")

    body = client.patch("/users/me", json={"city": "Lviv"}, headers=headers).json()

    assert body["stats"]["requests_count"] == 0
    assert "password_hash" not in body


def test_patch_null_clears_optional_fields(client: TestClient) -> None:
    headers = register(client, "me@example.com", phone="+380501234567", address="Kyiv")

    response = client.patch("/users/me", json={"phone": None, "address": None}, headers=headers)

    assert response.status_code == 200
    assert response.json()["phone"] is None
    assert response.json()["address"] is None


def test_duplicate_phone_is_rejected(client: TestClient) -> None:
    register(client, "a@example.com", phone="+380501234567")
    headers = register(client, "b@example.com")

    response = client.patch("/users/me", json={"phone": "+380501234567"}, headers=headers)

    assert response.status_code == 409


def test_own_phone_can_be_sent_again(client: TestClient) -> None:
    headers = register(client, "me@example.com", phone="+380501234567")

    response = client.patch("/users/me", json={"phone": "+380501234567"}, headers=headers)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"first_name": None},
        {"last_name": None},
        {"first_name": "   "},
        {"phone": "0501234567"},
        {"phone": "+380" + "\uff15" * 9},
        {"avatar_url": "not a url"},
        {"avatar_url": "ftp://example.com/a.png"},
        {"city": ""},
        {"email": "new@example.com"},
        {"role": "master"},
        {"public_id": 1},
    ],
)
def test_invalid_body_is_rejected(client: TestClient, body: dict) -> None:
    headers = register(client, "me@example.com")

    assert client.patch("/users/me", json=body, headers=headers).status_code == 422


def test_email_role_and_public_id_stay_the_same(client: TestClient, test_session_factory) -> None:
    headers = register(client, "me@example.com")
    before = get_user(test_session_factory, "me@example.com")

    client.patch("/users/me", json={"city": "Lviv"}, headers=headers)

    after = get_user(test_session_factory, "me@example.com")
    assert (after.email, after.role, after.public_id) == (
        before.email,
        before.role,
        before.public_id,
    )
