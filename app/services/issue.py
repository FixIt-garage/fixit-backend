from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.catalog import Category
from app.models.company import Company
from app.models.issue import Issue, IssueStatus
from app.models.issue_status_event import IssueStatusEvent
from app.models.master import Master
from app.models.user import User
from app.schemas.issue import IssueCreate, IssueUpdate


class CategoryNotFoundError(Exception):
    """Raised when an issue refers to a category that does not exist."""


class MasterNotFoundError(Exception):
    """Raised when an issue refers to a master that does not exist."""


class CompanyNotFoundError(Exception):
    """Raised when an issue refers to a service center that does not exist."""


class IssueNotFoundError(Exception):
    """Raised when an issue does not exist."""


class IssuePermissionError(Exception):
    """Raised when a user cannot perform an action on an issue."""


class InvalidStatusTransitionError(Exception):
    """Raised when an issue status transition is not allowed."""


def create_issue(db: Session, data: IssueCreate, owner: User) -> Issue:
    """Create an issue and record its initial status event."""
    if db.get(Category, data.category_id) is None:
        raise CategoryNotFoundError(data.category_id)

    if data.assignee_master_id is not None:
        master = db.get(Master, data.assignee_master_id)
        if master is None:
            raise MasterNotFoundError(data.assignee_master_id)

    if data.assignee_company_id is not None:
        company = db.get(Company, data.assignee_company_id)
        if company is None:
            raise CompanyNotFoundError(data.assignee_company_id)

    issue = Issue(
        **data.model_dump(),
        owner_id=owner.id,
        review_company_id=data.assignee_company_id,
    )
    db.add(issue)
    db.flush()

    event = IssueStatusEvent(
        issue_id=issue.id,
        status=IssueStatus.SENT,
        actor_id=owner.id,
    )
    db.add(event)

    db.commit()
    db.refresh(issue)
    return issue


def list_issues(
    db: Session,
    owner: User,
    *,
    limit: int,
    offset: int,
    status: IssueStatus | None = None,
    category_id: int | None = None,
) -> list[Issue]:
    """Return the owner's issues, newest first, with optional filters and pagination."""
    query = select(Issue).where(Issue.owner_id == owner.id, Issue.deleted_at.is_(None))

    if status is not None:
        query = query.where(Issue.status == status)
    if category_id is not None:
        query = query.where(Issue.category_id == category_id)

    query = query.order_by(Issue.created_at.desc(), Issue.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(query))


def list_my_issues(
    db: Session,
    owner: User,
    *,
    limit: int,
    offset: int,
    status_group: str | None = None,
    category_id: int | None = None,
) -> tuple[list[Issue], dict[str, int]]:
    """Return the owner's issues and counts for the status tabs."""
    base_query = select(Issue).where(
        Issue.owner_id == owner.id,
        Issue.deleted_at.is_(None),
    )

    if category_id is not None:
        base_query = base_query.where(Issue.category_id == category_id)

    counts_query = (
        select(
            func.count(Issue.id).label("all"),
            func.count(Issue.id)
            .filter(
                Issue.status.in_(
                    [
                        IssueStatus.SENT,
                        IssueStatus.ACCEPTED,
                        IssueStatus.IN_PROGRESS,
                    ]
                )
            )
            .label("active"),
            func.count(Issue.id).filter(Issue.status == IssueStatus.DONE).label("done"),
        )
        .select_from(Issue)
        .where(
            Issue.owner_id == owner.id,
            Issue.deleted_at.is_(None),
        )
    )

    if category_id is not None:
        counts_query = counts_query.where(Issue.category_id == category_id)

    counts_row = db.execute(counts_query).one()
    counts = {
        "all": counts_row.all,
        "active": counts_row.active,
        "done": counts_row.done,
    }

    if status_group == "active":
        base_query = base_query.where(
            Issue.status.in_(
                [
                    IssueStatus.SENT,
                    IssueStatus.ACCEPTED,
                    IssueStatus.IN_PROGRESS,
                ]
            )
        )
    elif status_group == "done":
        base_query = base_query.where(Issue.status == IssueStatus.DONE)

    issues = db.scalars(
        base_query.order_by(Issue.created_at.desc(), Issue.id.desc()).limit(limit).offset(offset)
    )

    return list(issues), counts


def get_issue(db: Session, issue_id: int, owner: User) -> Issue | None:
    """Return the owner's non-deleted issue by id, or None if there is no such issue."""
    return db.scalar(
        select(Issue).where(
            Issue.id == issue_id,
            Issue.owner_id == owner.id,
            Issue.deleted_at.is_(None),
        )
    )


def get_issue_details(db: Session, issue_id: int, actor: User):
    """Return issue details to its owner or assigned master."""
    issue = find_issue(db, issue_id)

    if issue is None:
        return None

    if issue.owner_id != actor.id:
        master = db.scalar(select(Master).where(Master.user_id == actor.id))

        if master is None:
            return None

        is_assigned_master = issue.assignee_master_id == master.id
        is_assigned_company = (
            master.company_id is not None and issue.assignee_company_id == master.company_id
        )

        if not (is_assigned_master or is_assigned_company):
            return None

    timeline = list(
        db.scalars(
            select(IssueStatusEvent)
            .where(IssueStatusEvent.issue_id == issue.id)
            .order_by(IssueStatusEvent.created_at.asc(), IssueStatusEvent.id.asc())
        )
    )

    assigned_master = None
    if issue.assignee_master_id is not None:
        assigned_master = db.get(Master, issue.assignee_master_id)

    master_user = None
    if assigned_master is not None:
        master_user = db.get(User, assigned_master.user_id)

    return issue, timeline, assigned_master, master_user


def find_issue(db: Session, issue_id: int) -> Issue | None:
    """Return a non-deleted issue by id regardless of its owner."""
    return db.scalar(select(Issue).where(Issue.id == issue_id, Issue.deleted_at.is_(None)))


def update_issue(db: Session, issue: Issue, data: IssueUpdate) -> Issue:
    """Apply only the fields that were sent in the request."""
    changes = data.model_dump(exclude_unset=True)

    category_id = changes.get("category_id")
    if category_id is not None and db.get(Category, category_id) is None:
        raise CategoryNotFoundError(category_id)

    for field, value in changes.items():
        setattr(issue, field, value)
    db.commit()
    db.refresh(issue)
    return issue


def delete_issue(db: Session, issue: Issue) -> None:
    """Soft delete: mark the issue as deleted instead of removing the row."""
    issue.deleted_at = datetime.now(UTC)
    db.commit()


def transition_issue(
    db: Session,
    issue_id: int,
    actor: User,
    target_status: IssueStatus,
) -> Issue:
    """Change issue status after checking permissions and record the event."""
    issue = db.scalar(
        select(Issue)
        .where(
            Issue.id == issue_id,
            Issue.deleted_at.is_(None),
        )
        .with_for_update()
    )

    if issue is None:
        raise IssueNotFoundError(issue_id)

    if target_status == IssueStatus.CANCELLED:
        if issue.owner_id != actor.id:
            raise IssuePermissionError("Only the issue owner can cancel it")

        allowed_statuses = {
            IssueStatus.SENT,
            IssueStatus.ACCEPTED,
            IssueStatus.IN_PROGRESS,
        }
    else:
        master = db.scalar(select(Master).where(Master.user_id == actor.id))

        if master is None:
            raise IssuePermissionError("Only an assigned master can perform this action")

        is_assigned_master = issue.assignee_master_id == master.id
        is_assigned_company_master = (
            issue.assignee_company_id is not None and master.company_id == issue.assignee_company_id
        )

        if not is_assigned_master and not is_assigned_company_master:
            raise IssuePermissionError("This issue is not assigned to you")

        allowed_statuses = {
            IssueStatus.SENT: {
                IssueStatus.ACCEPTED,
                IssueStatus.DECLINED,
            },
            IssueStatus.ACCEPTED: {
                IssueStatus.IN_PROGRESS,
            },
            IssueStatus.IN_PROGRESS: {
                IssueStatus.DONE,
            },
        }.get(issue.status, set())

    if target_status == IssueStatus.CANCELLED:
        if issue.status not in allowed_statuses:
            raise InvalidStatusTransitionError(
                f"Cannot change status from {issue.status} to {target_status}"
            )
    elif target_status not in allowed_statuses:
        raise InvalidStatusTransitionError(
            f"Cannot change status from {issue.status} to {target_status}"
        )

    if target_status == IssueStatus.ACCEPTED and issue.assignee_company_id is not None:
        issue.assignee_master_id = master.id
        issue.assignee_company_id = None

    issue.status = target_status

    db.add(
        IssueStatusEvent(
            issue_id=issue.id,
            status=target_status,
            actor_id=actor.id,
        )
    )

    db.commit()
    db.refresh(issue)

    return issue


def list_master_requests(
    db: Session,
    master_user: User,
    *,
    status: IssueStatus | None = None,
) -> list[dict]:
    """Return requests assigned to the master or their service center."""
    master = db.scalar(select(Master).where(Master.user_id == master_user.id))

    if master is None:
        return []

    assignment_conditions = [Issue.assignee_master_id == master.id]

    if master.company_id is not None:
        assignment_conditions.append(Issue.assignee_company_id == master.company_id)

    query = (
        select(Issue, User.first_name)
        .join(User, User.id == Issue.owner_id)
        .where(
            Issue.deleted_at.is_(None),
            or_(*assignment_conditions),
        )
    )

    if status is not None:
        query = query.where(Issue.status == status)

    rows = db.execute(query.order_by(Issue.created_at.desc(), Issue.id.desc())).all()

    now = datetime.now(UTC)
    result = []

    for issue, client_first_name in rows:
        created_at = issue.created_at

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        minutes = max(0, int((now - created_at).total_seconds() // 60))

        if minutes < 1:
            time_ago = "щойно"
        elif minutes < 60:
            time_ago = f"{minutes} хв тому"
        elif minutes < 1440:
            hours = minutes // 60
            time_ago = f"{hours} год тому"
        else:
            days = minutes // 1440
            time_ago = f"{days} дн тому"

        result.append(
            {
                "id": issue.id,
                "title": issue.title,
                "status": issue.status,
                "client_first_name": client_first_name,
                "district": issue.district,
                "time_ago": time_ago,
                "created_at": issue.created_at,
            }
        )

    return result
