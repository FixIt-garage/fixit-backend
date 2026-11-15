import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.user import User


def register(client: TestClient, email: str):
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User",
        },
    )


def login(client: TestClient, email: str):
    return client.post("/auth/login", json={"email": email, "password": "TestPassword123!"})


def test_email_is_trimmed_and_lowercased(client: TestClient, test_session_factory) -> None:
    assert register(client, "  Test@Example.COM ").status_code == 201

    with test_session_factory() as db:
        emails = db.scalars(select(User.email)).all()
    assert emails == ["test@example.com"]


def test_login_ignores_case_and_spaces(client: TestClient) -> None:
    register(client, "test@example.com")

    assert login(client, "TEST@example.com").status_code == 200
    assert login(client, "  test@example.com  ").status_code == 200


def test_email_differing_only_by_case_is_a_duplicate(client: TestClient) -> None:
    assert register(client, "test@example.com").status_code == 201

    assert register(client, "Test@Example.com").status_code == 409


def test_login_finds_a_legacy_email_stored_with_capitals(
    client: TestClient, test_session_factory
) -> None:
    register(client, "legacy@example.com")
    with test_session_factory() as db:
        user = db.scalar(select(User))
        user.email = "Legacy@Example.com"
        db.commit()

    assert login(client, "legacy@example.com").status_code == 200


@pytest.mark.parametrize(
    "email",
    [
        "",
        "   ",
        "plain",
        "no-at.example.com",
        "@example.com",
        "user@",
        "user@@example.com",
        "user name@example.com",
        "a" * 250 + "@example.com",
    ],
)
def test_invalid_email_is_rejected(client: TestClient, email: str) -> None:
    assert register(client, email).status_code == 422
    assert login(client, email).status_code == 422
