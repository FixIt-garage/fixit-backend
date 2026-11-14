from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.catalog import Category
from app.models.company import Company
from app.models.issue import Issue, IssueStatus
from app.models.issue_status_event import IssueStatusEvent
from app.models.master import Master
from app.models.user import User, UserRole
from app.services.issue import (
    InvalidStatusTransitionError,
    IssuePermissionError,
    transition_issue,
)


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


def test_concurrent_company_claim_has_one_winner(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        category_id = db.scalar(select(Category.id).order_by(Category.id))
        assert category_id is not None

        owner = create_test_user(db, "concurrent-owner@example.com", UserRole.CLIENT)
        first_user = create_test_user(db, "first-company-master@example.com", UserRole.MASTER)
        second_user = create_test_user(db, "second-company-master@example.com", UserRole.MASTER)

        company = Company(
            name="Concurrent Test Center",
            type="service_center",
        )
        db.add(company)
        db.flush()

        first_master = Master(
            user_id=first_user.id,
            company_id=company.id,
        )
        second_master = Master(
            user_id=second_user.id,
            company_id=company.id,
        )
        db.add_all([first_master, second_master])
        db.commit()

        owner_token = create_access_token(str(owner.id))
        company_id = company.id
        master_ids = {first_user.id: first_master.id, second_user.id: second_master.id}
        user_ids = [first_user.id, second_user.id]

    create_response = client.post(
        "/issues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Concurrent claim test",
            "description": "Two masters try to accept the same request",
            "category_id": category_id,
            "assignee_company_id": company_id,
        },
    )
    assert create_response.status_code == 201, create_response.json()
    issue_id = create_response.json()["id"]

    barrier = Barrier(2)

    def accept_as_master(user_id: int) -> tuple[str, int | str]:
        with test_session_factory() as db:
            actor = db.get(User, user_id)
            assert actor is not None

            barrier.wait(timeout=10)

            try:
                transition_issue(
                    db,
                    issue_id,
                    actor,
                    IssueStatus.ACCEPTED,
                )
                return ("success", user_id)
            except (IssuePermissionError, InvalidStatusTransitionError) as exc:
                db.rollback()
                return ("rejected", type(exc).__name__)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(accept_as_master, user_id) for user_id in user_ids]
        results = [future.result(timeout=30) for future in futures]

    successful_claims = [result for result in results if result[0] == "success"]
    rejected_claims = [result for result in results if result[0] == "rejected"]

    assert len(successful_claims) == 1
    assert len(rejected_claims) == 1

    winning_user_id = successful_claims[0][1]
    assert isinstance(winning_user_id, int)

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
        assert issue.status == IssueStatus.ACCEPTED
        assert issue.assignee_master_id == master_ids[winning_user_id]
        assert issue.assignee_company_id is None
        assert [event.status for event in events] == [
            IssueStatus.SENT,
            IssueStatus.ACCEPTED,
        ]


def test_concurrent_accept_and_cancel_preserves_cancellation(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        category_id = db.scalar(select(Category.id).order_by(Category.id))
        assert category_id is not None

        owner = create_test_user(db, "race-owner@example.com", UserRole.CLIENT)
        master_user = create_test_user(db, "race-master@example.com", UserRole.MASTER)

        master = Master(user_id=master_user.id)
        db.add(master)
        db.commit()

        owner_token = create_access_token(str(owner.id))
        master_id = master.id
        owner_id = owner.id
        master_user_id = master_user.id

    create_response = client.post(
        "/issues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Concurrent accept and cancel",
            "description": "Master accepts while owner cancels",
            "category_id": category_id,
            "assignee_master_id": master_id,
        },
    )
    assert create_response.status_code == 201, create_response.json()
    issue_id = create_response.json()["id"]

    barrier = Barrier(2)

    def perform_transition(
        user_id: int,
        target_status: IssueStatus,
        operation: str,
    ) -> tuple[str, str]:
        with test_session_factory() as db:
            actor = db.get(User, user_id)
            assert actor is not None

            barrier.wait(timeout=10)

            try:
                transition_issue(db, issue_id, actor, target_status)
                return ("success", operation)
            except InvalidStatusTransitionError:
                db.rollback()
                return ("rejected", operation)

    with ThreadPoolExecutor(max_workers=2) as executor:
        accept_future = executor.submit(
            perform_transition,
            master_user_id,
            IssueStatus.ACCEPTED,
            "accept",
        )
        cancel_future = executor.submit(
            perform_transition,
            owner_id,
            IssueStatus.CANCELLED,
            "cancel",
        )

        results = [
            accept_future.result(timeout=30),
            cancel_future.result(timeout=30),
        ]

    assert ("success", "cancel") in results
    assert results.count(("success", "accept")) <= 1

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
        assert issue.status == IssueStatus.CANCELLED

        event_statuses = [event.status for event in events]
        assert event_statuses in [
            [IssueStatus.SENT, IssueStatus.CANCELLED],
            [
                IssueStatus.SENT,
                IssueStatus.ACCEPTED,
                IssueStatus.CANCELLED,
            ],
        ]
        assert event_statuses.count(IssueStatus.ACCEPTED) <= 1
        assert events[-1].actor_id == owner_id


def test_assigned_master_can_decline_issue_and_status_event_is_created(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        category_id = db.scalar(select(Category.id).order_by(Category.id))
        assert category_id is not None

        owner = create_test_user(db, "decline-owner@example.com", UserRole.CLIENT)
        master_user = create_test_user(db, "decline-master@example.com", UserRole.MASTER)

        master = Master(user_id=master_user.id)
        db.add(master)
        db.commit()

        owner_token = create_access_token(str(owner.id))
        master_token = create_access_token(str(master_user.id))
        master_id = master.id
        master_user_id = master_user.id

    create_response = client.post(
        "/issues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "title": "Decline test",
            "description": "Request to be declined",
            "category_id": category_id,
            "assignee_master_id": master_id,
        },
    )
    assert create_response.status_code == 201, create_response.json()
    issue_id = create_response.json()["id"]

    decline_response = client.post(
        f"/issues/{issue_id}/decline",
        headers={"Authorization": f"Bearer {master_token}"},
    )

    assert decline_response.status_code == 200, decline_response.json()
    assert decline_response.json()["status"] == "declined"

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
        assert issue.status == IssueStatus.DECLINED
        assert [event.status for event in events] == [
            IssueStatus.SENT,
            IssueStatus.DECLINED,
        ]
        assert events[-1].actor_id == master_user_id


def test_all_invalid_status_transitions_are_rejected(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        category_id = db.scalar(select(Category.id).order_by(Category.id))
        assert category_id is not None

        owner = create_test_user(db, "matrix-owner@example.com", UserRole.CLIENT)
        master_user = create_test_user(db, "matrix-master@example.com", UserRole.MASTER)

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
            "title": "Status transition matrix",
            "description": "Testing all invalid status transitions",
            "category_id": category_id,
            "assignee_master_id": master_id,
        },
    )
    assert create_response.status_code == 201, create_response.json()
    issue_id = create_response.json()["id"]

    master_headers = {"Authorization": f"Bearer {master_token}"}
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    invalid_transitions = {
        IssueStatus.SENT: ["start", "complete"],
        IssueStatus.ACCEPTED: ["accept", "decline", "complete"],
        IssueStatus.IN_PROGRESS: ["accept", "decline", "start"],
        IssueStatus.DONE: ["accept", "decline", "start", "complete", "cancel"],
        IssueStatus.DECLINED: ["accept", "decline", "start", "complete", "cancel"],
        IssueStatus.CANCELLED: ["accept", "decline", "start", "complete", "cancel"],
    }

    for initial_status, invalid_actions in invalid_transitions.items():
        with test_session_factory() as db:
            issue = db.get(Issue, issue_id)
            assert issue is not None

            issue.status = initial_status
            db.commit()

        for action in invalid_actions:
            headers = owner_headers if action == "cancel" else master_headers

            response = client.post(
                f"/issues/{issue_id}/{action}",
                headers=headers,
            )

            assert response.status_code == 409, (
                f"{initial_status.value} -> {action}: "
                f"expected 409, got {response.status_code}: {response.text}"
            )

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
                assert issue.status == initial_status
                assert len(events) == 1
                assert events[0].status == IssueStatus.SENT
