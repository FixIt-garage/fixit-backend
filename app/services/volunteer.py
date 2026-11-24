from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import Category
from app.models.user import User
from app.models.volunteer import (
    VolunteerOrganization,
    VolunteerParticipation,
    VolunteerRequest,
    VolunteerRequestStatus,
)

PARTICIPANTS_SHOWN = 10


class VolunteerRequestNotFoundError(Exception):
    """The volunteer request does not exist."""


class JoinNotAllowedError(Exception):
    """The user cannot join the request; the message tells why."""


class NotJoinedError(Exception):
    """The user has not joined the request."""


class CategoryNotFoundError(Exception):
    """The category does not exist."""


class NotYourRequestError(Exception):
    """The request belongs to another organization."""


class UpdateNotAllowedError(Exception):
    """The change conflicts with the current state; the message tells why."""


def _joined_counts(db: Session, request_ids: list[int]) -> dict[int, int]:
    if not request_ids:
        return {}
    rows = db.execute(
        select(VolunteerParticipation.request_id, func.count())
        .where(VolunteerParticipation.request_id.in_(request_ids))
        .group_by(VolunteerParticipation.request_id)
    )
    return {request_id: count for request_id, count in rows}


def _joined_by(db: Session, request_ids: list[int], user: User) -> set[int]:
    if not request_ids:
        return set()
    return set(
        db.scalars(
            select(VolunteerParticipation.request_id).where(
                VolunteerParticipation.request_id.in_(request_ids),
                VolunteerParticipation.user_id == user.id,
            )
        )
    )


def _request_data(request: VolunteerRequest, joined: int, is_joined: bool) -> dict:
    organization = request.organization
    return {
        "id": request.id,
        "title": request.title,
        "description": request.description,
        "category_id": request.category_id,
        "address": request.address,
        "city": request.city,
        "district": request.district,
        "event_date": request.event_date,
        "status": request.status,
        "joined": joined,
        "needed": request.volunteers_needed,
        "is_joined": is_joined,
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "is_verified": organization.is_verified,
        },
    }


def list_requests(db: Session, user: User, city: str | None, limit: int, offset: int) -> dict:
    """Open requests that have not happened yet, the nearest first, undated ones last."""
    conditions = [
        VolunteerRequest.status == VolunteerRequestStatus.open,
        or_(VolunteerRequest.event_date.is_(None), VolunteerRequest.event_date >= func.now()),
    ]
    city = city.strip() if city else None
    if city:
        conditions.append(func.lower(VolunteerRequest.city) == city.lower())

    total = db.scalar(select(func.count()).select_from(VolunteerRequest).where(*conditions))
    requests = db.scalars(
        select(VolunteerRequest)
        .where(*conditions)
        .options(selectinload(VolunteerRequest.organization))
        .order_by(VolunteerRequest.event_date.asc().nulls_last(), VolunteerRequest.id)
        .limit(limit)
        .offset(offset)
    ).all()

    ids = [request.id for request in requests]
    counts = _joined_counts(db, ids)
    mine = _joined_by(db, ids, user)
    return {
        "items": [
            _request_data(request, counts.get(request.id, 0), request.id in mine)
            for request in requests
        ],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


def get_request(db: Session, user: User, request_id: int) -> dict:
    """One request (any status) with the latest participants."""
    request = db.scalar(
        select(VolunteerRequest)
        .where(VolunteerRequest.id == request_id)
        .options(selectinload(VolunteerRequest.organization))
    )
    if request is None:
        raise VolunteerRequestNotFoundError(request_id)

    joined = _joined_counts(db, [request.id]).get(request.id, 0)
    participants = db.scalars(
        select(User)
        .join(VolunteerParticipation, VolunteerParticipation.user_id == User.id)
        .where(VolunteerParticipation.request_id == request.id)
        .order_by(VolunteerParticipation.joined_at.desc(), User.id.desc())
        .limit(PARTICIPANTS_SHOWN)
    ).all()

    data = _request_data(request, joined, bool(_joined_by(db, [request.id], user)))
    data["participants"] = [
        {"id": person.id, "first_name": person.first_name, "avatar_url": person.avatar_url}
        for person in participants
    ]
    return data


def _lock_request(db: Session, request_id: int) -> VolunteerRequest:
    """Load the request and lock its row, so joins of one request go one after another."""
    request = db.scalar(
        select(VolunteerRequest).where(VolunteerRequest.id == request_id).with_for_update()
    )
    if request is None:
        raise VolunteerRequestNotFoundError(request_id)
    return request


def join_request(db: Session, user: User, request_id: int) -> dict:
    """Join an open request that has not happened yet and still has free places."""
    request = _lock_request(db, request_id)

    if request.status != VolunteerRequestStatus.open:
        raise JoinNotAllowedError("The request is closed")
    if request.event_date is not None and request.event_date < datetime.now(UTC):
        raise JoinNotAllowedError("The event has already happened")
    if _joined_by(db, [request.id], user):
        raise JoinNotAllowedError("You have already joined this request")
    joined = _joined_counts(db, [request.id]).get(request.id, 0)
    if request.volunteers_needed is not None and joined >= request.volunteers_needed:
        raise JoinNotAllowedError("The request is full")

    db.add(VolunteerParticipation(request_id=request.id, user_id=user.id))
    db.commit()
    return get_request(db, user, request_id)


def leave_request(db: Session, user: User, request_id: int) -> None:
    """Take the user off the request."""
    request = _lock_request(db, request_id)
    participation = db.get(VolunteerParticipation, (request.id, user.id))
    if participation is None:
        raise NotJoinedError(request_id)
    db.delete(participation)
    db.commit()


def get_organization(db: Session, user: User) -> VolunteerOrganization | None:
    return db.scalar(
        select(VolunteerOrganization).where(VolunteerOrganization.owner_user_id == user.id)
    )


def _check_category(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise CategoryNotFoundError(category_id)


def create_request(db: Session, user: User, organization: VolunteerOrganization, data) -> dict:
    """Publish an open request for the organization."""
    _check_category(db, data.category_id)
    request = VolunteerRequest(organization_id=organization.id, **data.model_dump())
    db.add(request)
    db.commit()
    return get_request(db, user, request.id)


def update_request(
    db: Session, user: User, organization: VolunteerOrganization, request_id: int, data
) -> dict:
    """Change only the sent fields of the organization's own request."""
    request = _lock_request(db, request_id)
    if request.organization_id != organization.id:
        raise NotYourRequestError(request_id)

    changes = data.model_dump(exclude_unset=True)
    if changes.get("category_id") is not None:
        _check_category(db, changes["category_id"])
    needed = changes.get("volunteers_needed")
    if needed is not None and needed < _joined_counts(db, [request.id]).get(request.id, 0):
        raise UpdateNotAllowedError("Fewer places than volunteers who have already joined")

    for field, value in changes.items():
        setattr(request, field, value)
    db.commit()
    return get_request(db, user, request_id)
