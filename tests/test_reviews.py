from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.catalog import Category
from app.models.company import Company
from app.models.issue import Issue, IssueStatus
from app.models.master import Master
from app.models.review import Review
from app.models.user import User, UserRole


def create_test_user(db, email: str, role: UserRole) -> User:
    user = User(
        email=email,
        password_hash="not-used-in-tests",
        first_name="Test",
        last_name="User",
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def create_test_issue(
    db,
    owner_id: int,
    master_id: int,
    status: IssueStatus = IssueStatus.DONE,
) -> Issue:
    category_id = db.scalar(select(Category.id).order_by(Category.id))
    assert category_id is not None

    issue = Issue(
        title="Broken washing machine",
        description="The washing machine does not work",
        category_id=category_id,
        owner_id=owner_id,
        assignee_master_id=master_id,
        status=status,
    )
    db.add(issue)
    db.flush()
    return issue


def setup_review_data(test_session_factory, email_prefix: str = "review"):
    with test_session_factory() as db:
        owner = create_test_user(
            db,
            f"{email_prefix}-owner@example.com",
            UserRole.CLIENT,
        )
        other_user = create_test_user(
            db,
            f"{email_prefix}-other@example.com",
            UserRole.CLIENT,
        )
        master_user = create_test_user(
            db,
            f"{email_prefix}-master@example.com",
            UserRole.MASTER,
        )

        master = Master(user_id=master_user.id)
        db.add(master)
        db.flush()

        issue = create_test_issue(db, owner.id, master.id)

        result = {
            "owner_token": create_access_token(str(owner.id)),
            "other_token": create_access_token(str(other_user.id)),
            "issue_id": issue.id,
            "master_id": master.id,
            "owner_id": owner.id,
        }
        db.commit()

    return result


def review_payload(rating: int = 5) -> dict:
    return {
        "rating": rating,
        "tags": ["Вчасно", "Якісно"],
        "comment": "Everything was done well",
    }


def test_client_can_review_completed_issue(
    client: TestClient,
    test_session_factory,
) -> None:
    data = setup_review_data(test_session_factory)

    response = client.post(
        f"/issues/{data['issue_id']}/review",
        headers={"Authorization": f"Bearer {data['owner_token']}"},
        json=review_payload(),
    )

    assert response.status_code == 201
    body = response.json()

    assert body["issue_id"] == data["issue_id"]
    assert body["master_id"] == data["master_id"]
    assert body["company_id"] is None
    assert body["rating"] == 5
    assert body["tags"] == ["Вчасно", "Якісно"]
    assert body["comment"] == "Everything was done well"
    assert body["author_first_name"] == "Test"

    with test_session_factory() as db:
        review = db.scalar(
            select(Review).where(Review.issue_id == data["issue_id"])
        )
        master = db.get(Master, data["master_id"])

        assert review is not None
        assert master is not None
        assert master.rating == Decimal("5.00")
        assert master.reviews_count == 1


def test_duplicate_review_returns_409(
    client: TestClient,
    test_session_factory,
) -> None:
    data = setup_review_data(test_session_factory, "duplicate")

    headers = {"Authorization": f"Bearer {data['owner_token']}"}
    url = f"/issues/{data['issue_id']}/review"

    first_response = client.post(url, headers=headers, json=review_payload())
    second_response = client.post(url, headers=headers, json=review_payload())

    assert first_response.status_code == 201
    assert second_response.status_code == 409

    with test_session_factory() as db:
        reviews = list(db.scalars(select(Review)))
        assert len(reviews) == 1


def test_review_for_non_completed_issue_returns_409(
    client: TestClient,
    test_session_factory,
) -> None:
    data = setup_review_data(test_session_factory, "not-done")

    with test_session_factory() as db:
        issue = db.get(Issue, data["issue_id"])
        assert issue is not None
        issue.status = IssueStatus.IN_PROGRESS
        db.commit()

    response = client.post(
        f"/issues/{data['issue_id']}/review",
        headers={"Authorization": f"Bearer {data['owner_token']}"},
        json=review_payload(),
    )

    assert response.status_code == 409

    with test_session_factory() as db:
        assert db.scalar(select(Review.id)) is None


def test_review_with_unknown_target_returns_409(
    client: TestClient,
    test_session_factory,
) -> None:
    data = setup_review_data(test_session_factory, "unknown-target")

    with test_session_factory() as db:
        issue = db.get(Issue, data["issue_id"])
        assert issue is not None
        issue.review_target_unknown = True
        db.commit()

    response = client.post(
        f"/issues/{data['issue_id']}/review",
        headers={"Authorization": f"Bearer {data['owner_token']}"},
        json=review_payload(),
    )

    assert response.status_code == 409

    with test_session_factory() as db:
        assert db.scalar(
            select(Review.id).where(Review.issue_id == data["issue_id"])
        ) is None

        master = db.get(Master, data["master_id"])
        assert master is not None
        assert master.rating is None
        assert master.reviews_count == 0


def test_non_owner_cannot_review_issue(
    client: TestClient,
    test_session_factory,
) -> None:
    data = setup_review_data(test_session_factory, "non-owner")

    response = client.post(
        f"/issues/{data['issue_id']}/review",
        headers={"Authorization": f"Bearer {data['other_token']}"},
        json=review_payload(),
    )

    assert response.status_code == 403

    with test_session_factory() as db:
        assert db.scalar(select(Review.id)) is None


def test_master_rating_is_recalculated_after_each_review(
    client: TestClient,
    test_session_factory,
) -> None:
    data = setup_review_data(test_session_factory, "aggregation")

    with test_session_factory() as db:
        second_issue = create_test_issue(
            db,
            data["owner_id"],
            data["master_id"],
        )
        second_issue_id = second_issue.id
        db.commit()

    headers = {"Authorization": f"Bearer {data['owner_token']}"}

    first_response = client.post(
        f"/issues/{data['issue_id']}/review",
        headers=headers,
        json=review_payload(5),
    )
    second_response = client.post(
        f"/issues/{second_issue_id}/review",
        headers=headers,
        json=review_payload(3),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    with test_session_factory() as db:
        master = db.get(Master, data["master_id"])

        assert master is not None
        assert master.rating == Decimal("4.00")
        assert master.reviews_count == 2

def test_company_review_updates_company_rating(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        owner = create_test_user(
            db, "company-review-owner@example.com", UserRole.CLIENT
        )
        master_user = create_test_user(
            db, "company-review-master@example.com", UserRole.MASTER
        )

        company = Company(name="Review Service Center", type="service_center")
        db.add(company)
        db.flush()

        master = Master(user_id=master_user.id, company_id=company.id)
        db.add(master)
        db.flush()

        issue = create_test_issue(db, owner.id, master.id)
        issue.review_company_id = company.id

        owner_token = create_access_token(str(owner.id))
        issue_id = issue.id
        company_id = company.id
        master_id = master.id
        db.commit()

    response = client.post(
        f"/issues/{issue_id}/review",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=review_payload(5),
    )

    assert response.status_code == 201
    assert response.json()["company_id"] == company_id
    assert response.json()["master_id"] is None

    with test_session_factory() as db:
        company = db.get(Company, company_id)
        master = db.get(Master, master_id)

        assert company is not None
        assert company.rating == Decimal("5.00")
        assert company.reviews_count == 1

        assert master is not None
        assert master.rating is None
        assert master.reviews_count == 0


def test_get_master_reviews_supports_pagination(
    client: TestClient,
    test_session_factory,
) -> None:
    data = setup_review_data(test_session_factory, "master-pagination")

    with test_session_factory() as db:
        second_issue = create_test_issue(
            db, data["owner_id"], data["master_id"]
        )
        second_issue_id = second_issue.id
        db.commit()

    headers = {"Authorization": f"Bearer {data['owner_token']}"}

    first = client.post(
        f"/issues/{data['issue_id']}/review",
        headers=headers,
        json=review_payload(5),
    )
    second = client.post(
        f"/issues/{second_issue_id}/review",
        headers=headers,
        json=review_payload(3),
    )

    assert first.status_code == 201
    assert second.status_code == 201

    response = client.get(
        f"/masters/{data['master_id']}/reviews?limit=1&offset=0"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    assert body["items"][0]["rating"] == 3
    assert body["items"][0]["author_first_name"] == "Test"


def test_get_service_center_reviews_supports_pagination(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        owner = create_test_user(
            db, "company-pagination-owner@example.com", UserRole.CLIENT
        )
        master_user = create_test_user(
            db, "company-pagination-master@example.com", UserRole.MASTER
        )

        company = Company(name="Pagination Service Center")
        db.add(company)
        db.flush()

        master = Master(user_id=master_user.id, company_id=company.id)
        db.add(master)
        db.flush()

        first_issue = create_test_issue(db, owner.id, master.id)
        second_issue = create_test_issue(db, owner.id, master.id)

        first_issue.review_company_id = company.id
        second_issue.review_company_id = company.id

        owner_token = create_access_token(str(owner.id))
        company_id = company.id
        first_issue_id = first_issue.id
        second_issue_id = second_issue.id
        db.commit()

    headers = {"Authorization": f"Bearer {owner_token}"}

    first = client.post(
        f"/issues/{first_issue_id}/review",
        headers=headers,
        json=review_payload(5),
    )
    second = client.post(
        f"/issues/{second_issue_id}/review",
        headers=headers,
        json=review_payload(3),
    )

    assert first.status_code == 201
    assert second.status_code == 201

    response = client.get(
        f"/service-centers/{company_id}/reviews?limit=1&offset=1"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["rating"] == 5