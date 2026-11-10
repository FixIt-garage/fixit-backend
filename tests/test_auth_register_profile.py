import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.user import User, UserRole


def register(client: TestClient, **overrides):
    payload = {
        "email": "new@example.com",
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "User",
    }
    payload.update(overrides)
    return client.post("/auth/register", json=payload)


def get_user(test_session_factory, email: str = "new@example.com") -> User:
    with test_session_factory() as db:
        user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def test_register_saves_profile_fields_and_role(client: TestClient, test_session_factory) -> None:
    response = register(
        client,
        phone="+380501234567",
        address="Lviv, Shevchenka 1",
        role="master",
    )

    assert response.status_code == 201
    user = get_user(test_session_factory)
    assert user.phone == "+380501234567"
    assert user.address == "Lviv, Shevchenka 1"
    assert user.role == UserRole.MASTER


def test_register_without_optional_fields_still_works(
    client: TestClient, test_session_factory
) -> None:
    assert register(client).status_code == 201
    user = get_user(test_session_factory)
    assert user.phone is None
    assert user.address is None
    assert user.role == UserRole.CLIENT


def test_phone_with_separators_is_normalized(client: TestClient, test_session_factory) -> None:
    response = register(client, phone="+380 (50) 123-45-67")

    assert response.status_code == 201
    assert get_user(test_session_factory).phone == "+380501234567"


def test_duplicate_phone_is_rejected(client: TestClient) -> None:
    assert register(client, email="a@example.com", phone="+380501234567").status_code == 201

    response = register(client, email="b@example.com", phone="+380501234567")

    assert response.status_code == 409


@pytest.mark.parametrize(
    "phone",
    ["0501234567", "+38050123456", "+3805012345678", "+380abc1234567", "", "12345"],
)
def test_invalid_phone_is_rejected(client: TestClient, phone: str) -> None:
    assert register(client, phone=phone).status_code == 422


def test_blank_address_is_rejected(client: TestClient) -> None:
    assert register(client, address="   ").status_code == 422


def test_unknown_role_is_rejected(client: TestClient) -> None:
    assert register(client, role="superuser").status_code == 422
