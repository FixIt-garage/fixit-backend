from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.catalog import Category
from app.models.company import Company
from app.models.issue import Issue, IssueStatus
from app.models.master import Master
from app.models.user import User, UserRole


def create_user(db, email: str, role: UserRole, first_name: str) -> User:
    user = User(
        email=email,
        password_hash="not-used-in-tests",
        first_name=first_name,
        last_name="Test",
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def test_master_sees_direct_and_company_requests_but_not_others(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        category_id = db.scalar(select(Category.id).order_by(Category.id))
        assert category_id is not None

        owner = create_user(db, "inbox-owner@example.com", UserRole.CLIENT, "Client")
        master_user = create_user(db, "inbox-master@example.com", UserRole.MASTER, "Master")
        other_master_user = create_user(db, "inbox-other@example.com", UserRole.MASTER, "Other")

        company = Company(name="Test Service Center")
        db.add(company)
        db.flush()

        master = Master(
            user_id=master_user.id,
            company_id=company.id,
        )
        other_master = Master(user_id=other_master_user.id)
        db.add_all([master, other_master])
        db.flush()

        now = datetime.now(UTC)

        direct_issue = Issue(
            title="Direct request",
            description="Assigned directly to master",
            category_id=category_id,
            owner_id=owner.id,
            assignee_master_id=master.id,
            status=IssueStatus.SENT,
            created_at=now,
            district="Галицький",
        )
        company_issue = Issue(
            title="Company request",
            description="Assigned to service center",
            category_id=category_id,
            owner_id=owner.id,
            assignee_company_id=company.id,
            status=IssueStatus.SENT,
            created_at=now - timedelta(minutes=5),
            district="Франківський",
        )
        other_issue = Issue(
            title="Other master request",
            description="Assigned to another master",
            category_id=category_id,
            owner_id=owner.id,
            assignee_master_id=other_master.id,
            status=IssueStatus.SENT,
        )
        unassigned_issue = Issue(
            title="Unassigned request",
            description="Not assigned",
            category_id=category_id,
            owner_id=owner.id,
            status=IssueStatus.SENT,
        )

        db.add_all([direct_issue, company_issue, other_issue, unassigned_issue])
        db.commit()

        token = create_access_token(str(master_user.id))

    response = client.get(
        "/masters/me/requests",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    requests = response.json()
    assert len(requests) == 2
    assert {item["title"] for item in requests} == {
        "Direct request",
        "Company request",
    }

    assert {item["title"]: item["district"] for item in requests} == {
        "Direct request": "Галицький",
        "Company request": "Франківський",
    }


def test_master_requests_filter_status_and_sort_newest_first(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        category_id = db.scalar(select(Category.id).order_by(Category.id))
        assert category_id is not None

        owner = create_user(db, "filter-owner@example.com", UserRole.CLIENT, "Client")
        master_user = create_user(db, "filter-master@example.com", UserRole.MASTER, "Master")
        master = Master(user_id=master_user.id)
        db.add(master)
        db.flush()

        now = datetime.now(UTC)

        db.add_all(
            [
                Issue(
                    title="Older sent request",
                    description="Older request",
                    category_id=category_id,
                    owner_id=owner.id,
                    assignee_master_id=master.id,
                    status=IssueStatus.SENT,
                    created_at=now - timedelta(minutes=10),
                ),
                Issue(
                    title="Newer sent request",
                    description="Newer request",
                    category_id=category_id,
                    owner_id=owner.id,
                    assignee_master_id=master.id,
                    status=IssueStatus.SENT,
                    created_at=now,
                ),
                Issue(
                    title="Accepted request",
                    description="Already accepted",
                    category_id=category_id,
                    owner_id=owner.id,
                    assignee_master_id=master.id,
                    status=IssueStatus.ACCEPTED,
                    created_at=now - timedelta(minutes=2),
                ),
            ]
        )
        db.commit()

        token = create_access_token(str(master_user.id))

    response = client.get(
        "/masters/me/requests?status=sent",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    requests = response.json()
    assert len(requests) == 2
    assert [item["title"] for item in requests] == [
        "Newer sent request",
        "Older sent request",
    ]
    assert all(item["status"] == "sent" for item in requests)
    assert all(item["client_first_name"] == "Client" for item in requests)
    assert all(item["district"] is None for item in requests)
    assert all(item["time_ago"] for item in requests)


def test_client_cannot_access_master_requests(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        client_user = create_user(db, "inbox-client@example.com", UserRole.CLIENT, "Client")
        db.commit()
        token = create_access_token(str(client_user.id))

    response = client.get(
        "/masters/me/requests",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
