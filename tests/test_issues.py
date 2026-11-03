import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.catalog import Category
from app.models.issue import Issue
from app.models.user import User


@pytest.fixture
def category_id(test_session_factory) -> int:
    """Id of a real category created by the seed migration."""
    with test_session_factory() as db:
        value = db.scalar(select(Category.id).order_by(Category.id))
    assert value is not None
    return value


@pytest.fixture
def payload(category_id: int) -> dict:
    return {
        "title": "Leaking tap",
        "description": "The kitchen tap has been leaking for two days",
        "category_id": category_id,
        "address": "Lviv, Shevchenka 1",
    }


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


def test_create_issue_returns_201_with_defaults(client: TestClient, payload: dict) -> None:
    response = client.post("/issues", json=payload, headers=auth_headers(client))

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["title"] == payload["title"]
    assert body["description"] == payload["description"]
    assert body["category_id"] == payload["category_id"]
    assert body["address"] == payload["address"]
    assert body["status"] == "open"
    assert body["created_at"]
    assert body["updated_at"]


def test_create_issue_owner_is_current_user(
    client: TestClient, test_session_factory, payload: dict
) -> None:
    headers = auth_headers(client, "owner@example.com")

    response = client.post("/issues", json=payload, headers=headers)

    assert response.status_code == 201
    with test_session_factory() as db:
        user = db.scalar(select(User).where(User.email == "owner@example.com"))
    assert user is not None
    assert response.json()["owner_id"] == user.id


def test_create_issue_is_saved_in_database(
    client: TestClient, test_session_factory, payload: dict
) -> None:
    response = client.post("/issues", json=payload, headers=auth_headers(client))

    assert response.status_code == 201
    with test_session_factory() as db:
        issue = db.get(Issue, response.json()["id"])
    assert issue is not None
    assert issue.title == payload["title"]
    assert issue.category_id == payload["category_id"]
    assert issue.deleted_at is None


def test_create_issue_ignores_owner_and_status_from_body(
    client: TestClient, payload: dict
) -> None:
    body = {**payload, "owner_id": 999, "status": "closed"}

    response = client.post("/issues", json=body, headers=auth_headers(client))

    assert response.status_code == 201
    assert response.json()["owner_id"] != 999
    assert response.json()["status"] == "open"


def test_create_issue_address_is_optional(client: TestClient, payload: dict) -> None:
    body = {key: value for key, value in payload.items() if key != "address"}

    response = client.post("/issues", json=body, headers=auth_headers(client))

    assert response.status_code == 201
    assert response.json()["address"] is None


def test_create_issue_without_token_is_rejected(client: TestClient, payload: dict) -> None:
    response = client.post("/issues", json=payload)

    assert response.status_code == 401


def test_create_issue_with_empty_title_is_rejected(client: TestClient, payload: dict) -> None:
    body = {**payload, "title": ""}

    response = client.post("/issues", json=body, headers=auth_headers(client))

    assert response.status_code == 422


def test_create_issue_without_description_is_rejected(
    client: TestClient, payload: dict
) -> None:
    body = {key: value for key, value in payload.items() if key != "description"}

    response = client.post("/issues", json=body, headers=auth_headers(client))

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["title", "description"])
def test_create_issue_with_whitespace_only_field_is_rejected(
    client: TestClient, payload: dict, field: str
) -> None:
    body = {**payload, field: " \t\n "}

    response = client.post("/issues", json=body, headers=auth_headers(client))

    assert response.status_code == 422


def test_create_issue_strips_surrounding_whitespace(client: TestClient, payload: dict) -> None:
    body = {**payload, "title": "  Leaking tap  ", "description": "\tNo water\n"}

    response = client.post("/issues", json=body, headers=auth_headers(client))

    assert response.status_code == 201
    assert response.json()["title"] == "Leaking tap"
    assert response.json()["description"] == "No water"


def test_create_issue_with_unknown_category_is_rejected(
    client: TestClient, payload: dict
) -> None:
    body = {**payload, "category_id": 999999}

    response = client.post("/issues", json=body, headers=auth_headers(client))

    assert response.status_code == 422
    assert response.json()["detail"] == "Category not found"


def test_create_issue_without_category_id_is_rejected(client: TestClient, payload: dict) -> None:
    body = {key: value for key, value in payload.items() if key != "category_id"}

    response = client.post("/issues", json=body, headers=auth_headers(client))

    assert response.status_code == 422