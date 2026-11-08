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
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_delete_returns_204_without_body(client: TestClient, category_id: int) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_id)

    response = client.delete(f"/issues/{created['id']}", headers=headers)

    assert response.status_code == 204
    assert response.content == b""


def test_delete_is_soft_delete(
    client: TestClient, test_session_factory, category_id: int
) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_id)

    client.delete(f"/issues/{created['id']}", headers=headers)

    with test_session_factory() as db:
        issue = db.get(Issue, created["id"])
    assert issue is not None
    assert issue.deleted_at is not None


def test_deleted_issue_disappears_from_get_and_list(
    client: TestClient, category_id: int
) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_id)

    client.delete(f"/issues/{created['id']}", headers=headers)

    assert client.get(f"/issues/{created['id']}", headers=headers).status_code == 404
    assert client.get("/issues", headers=headers).json() == []


def test_delete_twice_returns_404(client: TestClient, category_id: int) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_id)
    client.delete(f"/issues/{created['id']}", headers=headers)

    response = client.delete(f"/issues/{created['id']}", headers=headers)

    assert response.status_code == 404


def test_delete_by_another_user_is_forbidden(
    client: TestClient, test_session_factory, category_id: int
) -> None:
    alice = auth_headers(client, "alice@example.com")
    bob = auth_headers(client, "bob@example.com")
    created = create_issue(client, alice, category_id)

    response = client.delete(f"/issues/{created['id']}", headers=bob)

    assert response.status_code == 403
    with test_session_factory() as db:
        issue = db.get(Issue, created["id"])
    assert issue is not None
    assert issue.deleted_at is None


def test_delete_unknown_issue_returns_404(client: TestClient) -> None:
    response = client.delete("/issues/999999", headers=auth_headers(client))

    assert response.status_code == 404


def test_delete_without_token_is_rejected(client: TestClient) -> None:
    response = client.delete("/issues/1")

    assert response.status_code == 401


def test_patch_deleted_issue_returns_404(client: TestClient, category_id: int) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_id)
    client.delete(f"/issues/{created['id']}", headers=headers)

    response = client.patch(f"/issues/{created['id']}", json={"title": "x"}, headers=headers)

    assert response.status_code == 404