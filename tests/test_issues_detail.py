from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.catalog import Category
from app.models.issue import Issue


@pytest.fixture
def category_id(test_session_factory) -> int:
    """Id of a real category created by the seed migration."""
    with test_session_factory() as db:
        value = db.scalar(select(Category.id).order_by(Category.id))
    assert value is not None
    return value


def auth_headers(client: TestClient, email: str = "owner@example.com") -> dict[str, str]:
    """Register a user and return the Authorization header for that user."""
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_issue(client: TestClient, headers: dict[str, str], category_id: int) -> dict:
    response = client.post(
        "/issues",
        json={
            "title": "Leaking tap",
            "description": "The kitchen tap has been leaking",
            "category_id": category_id,
            "address": "Lviv, Shevchenka 1",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_get_issue_returns_own_issue(client: TestClient, category_id: int) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_id)

    response = client.get(f"/issues/{created['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json() == created


def test_get_issue_unknown_id_returns_404(client: TestClient) -> None:
    response = client.get("/issues/999999", headers=auth_headers(client))

    assert response.status_code == 404
    assert response.json()["message"] == "Issue not found"


def test_get_issue_of_another_user_returns_404(client: TestClient, category_id: int) -> None:
    alice = auth_headers(client, "alice@example.com")
    bob = auth_headers(client, "bob@example.com")
    created = create_issue(client, alice, category_id)

    response = client.get(f"/issues/{created['id']}", headers=bob)

    assert response.status_code == 404


def test_get_soft_deleted_issue_returns_404(
    client: TestClient, test_session_factory, category_id: int
) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_id)
    with test_session_factory() as db:
        db.get(Issue, created["id"]).deleted_at = datetime.now(UTC)
        db.commit()

    response = client.get(f"/issues/{created['id']}", headers=headers)

    assert response.status_code == 404


def test_get_issue_without_token_is_rejected(client: TestClient) -> None:
    response = client.get("/issues/1")

    assert response.status_code == 401


def test_get_issue_with_non_numeric_id_is_rejected(client: TestClient) -> None:
    response = client.get("/issues/abc", headers=auth_headers(client))

    assert response.status_code == 422