from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.catalog import Category
from app.models.issue import Issue
from app.models.master import Master
from app.models.user import User, UserRole


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
    body = response.json()

    for key, value in created.items():
        assert body[key] == value

    assert len(body["timeline"]) == 1
    assert body["timeline"][0]["status"] == "sent"
    assert body["timeline"][0]["actor_id"] == body["owner_id"]
    assert body["assigned_master"] is None


def test_get_issue_returns_assigned_master(
    client: TestClient,
    category_id: int,
    test_session_factory,
) -> None:
    owner_headers = auth_headers(client, "owner@example.com")
    auth_headers(client, "master@example.com")

    with test_session_factory() as db:
        master_user = db.scalar(select(User).where(User.email == "master@example.com"))
        assert master_user is not None

        master = Master(
            user_id=master_user.id,
            rating=Decimal("4.80"),
        )
        db.add(master)
        db.commit()
        db.refresh(master)
        master_id = master.id

    response = client.post(
        "/issues",
        json={
            "title": "Leaking tap",
            "description": "The kitchen tap has been leaking",
            "category_id": category_id,
            "assignee_master_id": master_id,
        },
        headers=owner_headers,
    )
    assert response.status_code == 201

    issue_id = response.json()["id"]

    detail_response = client.get(
        f"/issues/{issue_id}",
        headers=owner_headers,
    )

    assert detail_response.status_code == 200

    body = detail_response.json()
    assert body["assigned_master"] == {
        "name": "Test User",
        "rating": "4.80",
    }
    assert body["timeline"][0]["status"] == "sent"
    assert body["timeline"][0]["actor_id"] == body["owner_id"]


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


def test_assigned_master_can_view_issue_timeline(
    client: TestClient,
    category_id: int,
    test_session_factory,
) -> None:
    owner_headers = auth_headers(client, "timeline-owner@example.com")

    with test_session_factory() as db:
        master_user = User(
            email="timeline-master@example.com",
            password_hash="not-used-in-tests",
            first_name="Assigned",
            last_name="Master",
            role=UserRole.MASTER,
        )
        db.add(master_user)
        db.flush()

        master = Master(user_id=master_user.id)
        db.add(master)
        db.commit()

        master_id = master.id
        master_token = create_access_token(str(master_user.id))

    created = client.post(
        "/issues",
        json={
            "title": "Leaking tap",
            "description": "The kitchen tap has been leaking",
            "category_id": category_id,
            "assignee_master_id": master_id,
        },
        headers=owner_headers,
    )
    assert created.status_code == 201

    response = client.get(
        f"/issues/{created.json()['id']}",
        headers={"Authorization": f"Bearer {master_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Leaking tap"
    assert len(body["timeline"]) == 1
    assert body["timeline"][0]["status"] == "sent"
    assert body["timeline"][0]["actor_id"] == body["owner_id"]


def test_unassigned_master_cannot_view_issue(
    client: TestClient,
    category_id: int,
    test_session_factory,
) -> None:
    owner_headers = auth_headers(client, "private-owner@example.com")

    with test_session_factory() as db:
        master_user = User(
            email="unassigned-master@example.com",
            password_hash="not-used-in-tests",
            first_name="Other",
            last_name="Master",
            role=UserRole.MASTER,
        )
        db.add(master_user)
        db.commit()
        master_token = create_access_token(str(master_user.id))

    created = create_issue(client, owner_headers, category_id)

    response = client.get(
        f"/issues/{created['id']}",
        headers={"Authorization": f"Bearer {master_token}"},
    )

    assert response.status_code == 404
