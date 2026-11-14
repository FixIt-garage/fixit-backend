from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.catalog import Category
from app.models.company import Company
from app.models.issue import Issue, IssueStatus
from app.models.issue_status_event import IssueStatusEvent
from app.models.master import Master
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


def test_master_can_accept_start_and_complete_assigned_issue(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        category_id = db.scalar(select(Category.id).order_by(Category.id))
        assert category_id is not None

        owner = create_test_user(db, "flow-owner@example.com", UserRole.CLIENT)
        master_user = create_test_user(db, "flow-master@example.com", UserRole.MASTER)

        master = Master(user_id=master_user.id)
        db.add(master)
        db.commit()

        owner_token = create_access_token(str(owner.id))
        master_token = create_access_token(str(master_user.id))
        master_id = master.id

    create_response = client.post(
        "/issues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Leaking tap",
            "description": "The kitchen tap is leaking",
            "category_id": category_id,
            "assignee_master_id": master_id,
        },
    )

    assert create_response.status_code == 201
    issue_id = create_response.json()["id"]
    master_headers = {"Authorization": f"Bearer {master_token}"}

    accept_response = client.post(
        f"/issues/{issue_id}/accept",
        headers=master_headers,
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "accepted"

    start_response = client.post(
        f"/issues/{issue_id}/start",
        headers=master_headers,
    )
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "in_progress"

    complete_response = client.post(
        f"/issues/{issue_id}/complete",
        headers=master_headers,
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "done"

    with test_session_factory() as db:
        issue = db.get(Issue, issue_id)
        events = list(
            db.scalars(
                select(IssueStatusEvent)
                .where(IssueStatusEvent.issue_id == issue_id)
                .order_by(IssueStatusEvent.id)
            )
        )

        assert issue is not None
        assert issue.status == IssueStatus.DONE
        assert [event.status for event in events] == [
            IssueStatus.SENT,
            IssueStatus.ACCEPTED,
            IssueStatus.IN_PROGRESS,
            IssueStatus.DONE,
        ]
        assert events[0].actor_id == owner.id
        assert all(event.actor_id == master_user.id for event in events[1:])


def test_status_transition_checks_permissions_and_allowed_order(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        category_id = db.scalar(select(Category.id).order_by(Category.id))
        assert category_id is not None

        owner = create_test_user(db, "permissions-owner@example.com", UserRole.CLIENT)
        assigned_user = create_test_user(db, "assigned-master@example.com", UserRole.MASTER)
        other_user = create_test_user(db, "other-master@example.com", UserRole.MASTER)

        assigned_master = Master(user_id=assigned_user.id)
        other_master = Master(user_id=other_user.id)
        db.add_all([assigned_master, other_master])
        db.commit()

        owner_token = create_access_token(str(owner.id))
        assigned_token = create_access_token(str(assigned_user.id))
        other_token = create_access_token(str(other_user.id))
        assigned_master_id = assigned_master.id

    create_response = client.post(
        "/issues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Broken washing machine",
            "description": "The washing machine does not start",
            "category_id": category_id,
            "assignee_master_id": assigned_master_id,
        },
    )
    assert create_response.status_code == 201
    issue_id = create_response.json()["id"]

    # Майстер не може почати роботу, поки не прийняв заявку.
    start_response = client.post(
        f"/issues/{issue_id}/start",
        headers={"Authorization": f"Bearer {assigned_token}"},
    )
    assert start_response.status_code == 409

    # Інший майстер не може прийняти чужу заявку.
    accept_response = client.post(
        f"/issues/{issue_id}/accept",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert accept_response.status_code == 403

    # Після невдалих запитів статус має залишитися початковим.
    detail_response = client.get(
        f"/issues/{issue_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "sent"


def test_company_assigned_issue_is_claimed_by_company_master(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        category_id = db.scalar(select(Category.id).order_by(Category.id))
        assert category_id is not None

        owner = create_test_user(db, "company-owner@example.com", UserRole.CLIENT)
        master_user = create_test_user(db, "company-master@example.com", UserRole.MASTER)

        company = Company(
            name="Test Service Center",
            type="service_center",
        )
        db.add(company)
        db.flush()

        master = Master(
            user_id=master_user.id,
            company_id=company.id,
        )
        db.add(master)
        db.commit()

        owner_token = create_access_token(str(owner.id))
        master_token = create_access_token(str(master_user.id))
        company_id = company.id
        master_id = master.id

    create_response = client.post(
        "/issues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Broken refrigerator",
            "description": "The refrigerator is not cooling",
            "category_id": category_id,
            "assignee_company_id": company_id,
        },
    )

    assert create_response.status_code == 201
    issue_id = create_response.json()["id"]

    accept_response = client.post(
        f"/issues/{issue_id}/accept",
        headers={"Authorization": f"Bearer {master_token}"},
    )

    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "accepted"

    with test_session_factory() as db:
        issue = db.get(Issue, issue_id)

        assert issue is not None
        assert issue.assignee_master_id == master_id
        assert issue.assignee_company_id is None


def test_issue_owner_can_cancel_and_status_event_is_created(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        category_id = db.scalar(select(Category.id).order_by(Category.id))
        assert category_id is not None

        owner = create_test_user(db, "cancel-owner@example.com", UserRole.CLIENT)
        db.commit()

        owner_token = create_access_token(str(owner.id))
        owner_id = owner.id

    create_response = client.post(
        "/issues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Broken lamp",
            "description": "The lamp does not turn on",
            "category_id": category_id,
        },
    )
    assert create_response.status_code == 201
    issue_id = create_response.json()["id"]

    cancel_response = client.post(
        f"/issues/{issue_id}/cancel",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert cancel_response.status_code == 200, cancel_response.json()
    assert cancel_response.json()["status"] == "cancelled"

    with test_session_factory() as db:
        events = list(
            db.scalars(
                select(IssueStatusEvent)
                .where(IssueStatusEvent.issue_id == issue_id)
                .order_by(IssueStatusEvent.id)
            )
        )

        assert [event.status for event in events] == [
            IssueStatus.SENT,
            IssueStatus.CANCELLED,
        ]
        assert events[-1].actor_id == owner_id
