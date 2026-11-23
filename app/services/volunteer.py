from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.user import User
from app.models.volunteer import (
    VolunteerParticipation,
    VolunteerRequest,
    VolunteerRequestStatus,
)

PARTICIPANTS_SHOWN = 10


class VolunteerRequestNotFoundError(Exception):
    """The volunteer request does not exist."""


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
    """Open volunteer requests, the nearest events first, undated ones last."""
    conditions = [VolunteerRequest.status == VolunteerRequestStatus.open]
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
