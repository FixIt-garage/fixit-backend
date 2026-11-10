import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.catalog import Category
from app.models.issue import Issue


@pytest.fixture
def category_ids(test_session_factory) -> list[int]:
    """Ids of two real categories created by the seed migration."""
    with test_session_factory() as db:
        values = list(db.scalars(select(Category.id).order_by(Category.id).limit(2)))
    assert len(values) == 2
    return values


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


def test_patch_updates_only_sent_fields(client: TestClient, category_ids: list[int]) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_ids[0])

    response = client.patch(
        f"/issues/{created['id']}", json={"title": "New title"}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New title"
    assert body["description"] == created["description"]
    assert body["category_id"] == created["category_id"]
    assert body["address"] == created["address"]
    assert body["status"] == "open"


def test_patch_can_change_status_category_and_address(
    client: TestClient, category_ids: list[int]
) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_ids[0])

    response = client.patch(
        f"/issues/{created['id']}",
        json={"status": "in_progress", "category_id": category_ids[1], "address": "Kyiv"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["category_id"] == category_ids[1]
    assert body["address"] == "Kyiv"


def test_patch_is_saved_in_database(
    client: TestClient, test_session_factory, category_ids: list[int]
) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_ids[0])

    client.patch(f"/issues/{created['id']}", json={"title": "Saved"}, headers=headers)

    with test_session_factory() as db:
        issue = db.get(Issue, created["id"])
    assert issue is not None
    assert issue.title == "Saved"


def test_patch_null_address_clears_it(client: TestClient, category_ids: list[int]) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_ids[0])

    response = client.patch(f"/issues/{created['id']}", json={"address": None}, headers=headers)

    assert response.status_code == 200
    assert response.json()["address"] is None


def test_patch_strips_whitespace(client: TestClient, category_ids: list[int]) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_ids[0])

    response = client.patch(
        f"/issues/{created['id']}", json={"title": "  Trimmed  "}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Trimmed"


def test_patch_by_another_user_is_forbidden(
    client: TestClient, test_session_factory, category_ids: list[int]
) -> None:
    alice = auth_headers(client, "alice@example.com")
    bob = auth_headers(client, "bob@example.com")
    created = create_issue(client, alice, category_ids[0])

    response = client.patch(f"/issues/{created['id']}", json={"title": "Hacked"}, headers=bob)

    assert response.status_code == 403
    with test_session_factory() as db:
        issue = db.get(Issue, created["id"])
    assert issue is not None
    assert issue.title == created["title"]


def test_patch_unknown_issue_returns_404(client: TestClient) -> None:
    response = client.patch("/issues/999999", json={"title": "x"}, headers=auth_headers(client))

    assert response.status_code == 404


def test_patch_without_token_is_rejected(client: TestClient) -> None:
    response = client.patch("/issues/1", json={"title": "x"})

    assert response.status_code == 401


def test_patch_with_unknown_category_is_rejected(
    client: TestClient, category_ids: list[int]
) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_ids[0])

    response = client.patch(
        f"/issues/{created['id']}", json={"category_id": 999999}, headers=headers
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Category not found"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"title": None},
        {"description": None},
        {"category_id": None},
        {"status": None},
        {"title": "   "},
        {"description": "x" * 501},
        {"status": "unknown"},
        {"category_id": 0},
    ],
)
def test_patch_with_invalid_body_is_rejected(
    client: TestClient, category_ids: list[int], body: dict
) -> None:
    headers = auth_headers(client)
    created = create_issue(client, headers, category_ids[0])

    response = client.patch(f"/issues/{created['id']}", json=body, headers=headers)

    assert response.status_code == 422