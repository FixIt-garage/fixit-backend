from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.catalog import Category
from app.models.issue import Issue, IssueStatus


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


def create_issue(
    client: TestClient, headers: dict[str, str], category_id: int, title: str = "Issue"
) -> dict:
    response = client.post(
        "/issues",
        json={"title": title, "description": "Some description", "category_id": category_id},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def titles(response) -> list[str]:
    return [item["title"] for item in response.json()]


def test_list_is_empty_for_new_user(client: TestClient) -> None:
    response = client.get("/issues", headers=auth_headers(client))

    assert response.status_code == 200
    assert response.json() == []


def test_list_returns_only_own_issues(client: TestClient, category_ids: list[int]) -> None:
    alice = auth_headers(client, "alice@example.com")
    bob = auth_headers(client, "bob@example.com")
    create_issue(client, alice, category_ids[0], "alice-1")
    create_issue(client, alice, category_ids[0], "alice-2")
    create_issue(client, bob, category_ids[0], "bob-1")

    assert sorted(titles(client.get("/issues", headers=alice))) == ["alice-1", "alice-2"]
    assert titles(client.get("/issues", headers=bob)) == ["bob-1"]


def test_list_is_newest_first(client: TestClient, category_ids: list[int]) -> None:
    headers = auth_headers(client)
    for name in ["first", "second", "third"]:
        create_issue(client, headers, category_ids[0], name)

    response = client.get("/issues", headers=headers)

    assert titles(response) == ["third", "second", "first"]


def test_list_pagination_limit_and_offset(client: TestClient, category_ids: list[int]) -> None:
    headers = auth_headers(client)
    for index in range(5):
        create_issue(client, headers, category_ids[0], f"issue-{index}")

    assert titles(client.get("/issues?limit=2", headers=headers)) == ["issue-4", "issue-3"]
    page = client.get("/issues?limit=2&offset=2", headers=headers)
    assert titles(page) == ["issue-2", "issue-1"]
    assert titles(client.get("/issues?limit=2&offset=4", headers=headers)) == ["issue-0"]
    assert client.get("/issues?offset=10", headers=headers).json() == []


def test_list_filter_by_status(
    client: TestClient, test_session_factory, category_ids: list[int]
) -> None:
    headers = auth_headers(client)
    first = create_issue(client, headers, category_ids[0], "will-be-resolved")
    second = create_issue(client, headers, category_ids[0], "will-be-in-progress")
    create_issue(client, headers, category_ids[0], "stays-open")
    with test_session_factory() as db:
        db.get(Issue, first["id"]).status = IssueStatus.RESOLVED
        db.get(Issue, second["id"]).status = IssueStatus.IN_PROGRESS
        db.commit()

    resolved = client.get("/issues?status=resolved", headers=headers)
    in_progress = client.get("/issues?status=in_progress", headers=headers)
    still_open = client.get("/issues?status=open", headers=headers)

    assert titles(resolved) == ["will-be-resolved"]
    assert titles(in_progress) == ["will-be-in-progress"]
    assert titles(still_open) == ["stays-open"]


def test_list_filter_by_category(client: TestClient, category_ids: list[int]) -> None:
    headers = auth_headers(client)
    create_issue(client, headers, category_ids[0], "a")
    create_issue(client, headers, category_ids[1], "b")
    create_issue(client, headers, category_ids[0], "c")

    first_category = client.get(f"/issues?category_id={category_ids[0]}", headers=headers)
    second_category = client.get(f"/issues?category_id={category_ids[1]}", headers=headers)

    assert titles(first_category) == ["c", "a"]
    assert titles(second_category) == ["b"]


def test_list_excludes_soft_deleted_issues(
    client: TestClient, test_session_factory, category_ids: list[int]
) -> None:
    headers = auth_headers(client)
    deleted = create_issue(client, headers, category_ids[0], "deleted")
    create_issue(client, headers, category_ids[0], "kept")
    with test_session_factory() as db:
        db.get(Issue, deleted["id"]).deleted_at = datetime.now(UTC)
        db.commit()

    response = client.get("/issues", headers=headers)

    assert titles(response) == ["kept"]


def test_list_without_token_is_rejected(client: TestClient) -> None:
    response = client.get("/issues")

    assert response.status_code == 401


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=101", "offset=-1", "status=unknown", "category_id=0"],
)
def test_list_with_invalid_query_is_rejected(client: TestClient, query: str) -> None:
    response = client.get(f"/issues?{query}", headers=auth_headers(client))

    assert response.status_code == 422