from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.issue import Issue
from app.models.user import User

ISSUE_PAYLOAD = {
    "title": "Leaking tap",
    "description": "The kitchen tap has been leaking for two days",
    "category": "plumbing",
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


def test_create_issue_returns_201_with_defaults(client: TestClient) -> None:
    response = client.post("/issues", json=ISSUE_PAYLOAD, headers=auth_headers(client))

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["title"] == ISSUE_PAYLOAD["title"]
    assert body["description"] == ISSUE_PAYLOAD["description"]
    assert body["category"] == ISSUE_PAYLOAD["category"]
    assert body["address"] == ISSUE_PAYLOAD["address"]
    assert body["status"] == "open"
    assert body["created_at"]
    assert body["updated_at"]


def test_create_issue_owner_is_current_user(client: TestClient, test_session_factory) -> None:
    headers = auth_headers(client, "owner@example.com")

    response = client.post("/issues", json=ISSUE_PAYLOAD, headers=headers)

    assert response.status_code == 201
    with test_session_factory() as db:
        user = db.scalar(select(User).where(User.email == "owner@example.com"))
    assert user is not None
    assert response.json()["owner_id"] == user.id


def test_create_issue_is_saved_in_database(client: TestClient, test_session_factory) -> None:
    response = client.post("/issues", json=ISSUE_PAYLOAD, headers=auth_headers(client))

    assert response.status_code == 201
    with test_session_factory() as db:
        issue = db.get(Issue, response.json()["id"])
    assert issue is not None
    assert issue.title == ISSUE_PAYLOAD["title"]
    assert issue.deleted_at is None


def test_create_issue_ignores_owner_and_status_from_body(client: TestClient) -> None:
    payload = {**ISSUE_PAYLOAD, "owner_id": 999, "status": "closed"}

    response = client.post("/issues", json=payload, headers=auth_headers(client))

    assert response.status_code == 201
    assert response.json()["owner_id"] != 999
    assert response.json()["status"] == "open"


def test_create_issue_address_is_optional(client: TestClient) -> None:
    payload = {key: value for key, value in ISSUE_PAYLOAD.items() if key != "address"}

    response = client.post("/issues", json=payload, headers=auth_headers(client))

    assert response.status_code == 201
    assert response.json()["address"] is None


def test_create_issue_without_token_is_rejected(client: TestClient) -> None:
    response = client.post("/issues", json=ISSUE_PAYLOAD)

    assert response.status_code == 401


def test_create_issue_with_empty_title_is_rejected(client: TestClient) -> None:
    payload = {**ISSUE_PAYLOAD, "title": ""}

    response = client.post("/issues", json=payload, headers=auth_headers(client))

    assert response.status_code == 422


def test_create_issue_without_description_is_rejected(client: TestClient) -> None:
    payload = {key: value for key, value in ISSUE_PAYLOAD.items() if key != "description"}

    response = client.post("/issues", json=payload, headers=auth_headers(client))

    assert response.status_code == 422
