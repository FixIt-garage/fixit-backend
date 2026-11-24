import pytest
from sqlalchemy import select

from app.models.volunteer import VolunteerParticipation, VolunteerRequestStatus
from tests.test_volunteer_requests import make_volunteer, register, seed_requests, user_id


@pytest.fixture
def volunteer(client, test_session_factory) -> dict[str, str]:
    return make_volunteer(client, test_session_factory)


def joined_ids(factory, request_id: int) -> list[int]:
    with factory() as db:
        return sorted(
            db.scalars(
                select(VolunteerParticipation.user_id).where(
                    VolunteerParticipation.request_id == request_id
                )
            )
        )


def test_join_adds_the_user_and_returns_the_request(
    client, test_session_factory, volunteer
) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help", "needed": 3})

    response = client.post(f"/volunteer-requests/{request_id}/join", headers=volunteer)

    assert response.status_code == 200
    body = response.json()
    assert (body["joined"], body["needed"], body["is_joined"]) == (1, 3, True)
    assert [person["first_name"] for person in body["participants"]] == ["Test"]
    assert joined_ids(test_session_factory, request_id) == [
        user_id(test_session_factory, "volunteer@example.com")
    ]


def test_joining_twice_is_a_conflict(client, test_session_factory, volunteer) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help"})
    client.post(f"/volunteer-requests/{request_id}/join", headers=volunteer)

    response = client.post(f"/volunteer-requests/{request_id}/join", headers=volunteer)

    assert response.status_code == 409
    assert response.json()["detail"] == "You have already joined this request"
    assert len(joined_ids(test_session_factory, request_id)) == 1


def test_full_request_does_not_take_more_people(client, test_session_factory, volunteer) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help", "needed": 1})
    other = make_volunteer(client, test_session_factory, "other@example.com")
    assert client.post(f"/volunteer-requests/{request_id}/join", headers=other).status_code == 200

    response = client.post(f"/volunteer-requests/{request_id}/join", headers=volunteer)

    assert response.status_code == 409
    assert response.json()["detail"] == "The request is full"
    assert len(joined_ids(test_session_factory, request_id)) == 1


def test_request_without_a_limit_takes_everybody(client, test_session_factory, volunteer) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help", "needed": None})
    other = make_volunteer(client, test_session_factory, "other@example.com")

    first = client.post(f"/volunteer-requests/{request_id}/join", headers=other)
    second = client.post(f"/volunteer-requests/{request_id}/join", headers=volunteer)

    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json()["joined"] == 2


def test_closed_and_past_requests_cannot_be_joined(client, test_session_factory, volunteer) -> None:
    closed_id, past_id = seed_requests(
        test_session_factory,
        {"title": "Closed", "status": VolunteerRequestStatus.closed},
        {"title": "Past", "days": -1},
    )

    closed = client.post(f"/volunteer-requests/{closed_id}/join", headers=volunteer)
    past = client.post(f"/volunteer-requests/{past_id}/join", headers=volunteer)

    assert (closed.status_code, closed.json()["detail"]) == (409, "The request is closed")
    assert (past.status_code, past.json()["detail"]) == (409, "The event has already happened")


def test_leave_removes_the_user_and_frees_the_place(
    client, test_session_factory, volunteer
) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help", "needed": 1})
    client.post(f"/volunteer-requests/{request_id}/join", headers=volunteer)

    leave = client.delete(f"/volunteer-requests/{request_id}/join", headers=volunteer)
    other = make_volunteer(client, test_session_factory, "other@example.com")
    again = client.post(f"/volunteer-requests/{request_id}/join", headers=other)

    assert leave.status_code == 204
    assert leave.content == b""
    assert again.status_code == 200


def test_leave_without_joining_is_not_found(client, test_session_factory, volunteer) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help"})

    response = client.delete(f"/volunteer-requests/{request_id}/join", headers=volunteer)

    assert response.status_code == 404


def test_one_user_leaving_does_not_remove_the_others(
    client, test_session_factory, volunteer
) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help", "needed": 5})
    other = make_volunteer(client, test_session_factory, "other@example.com")
    client.post(f"/volunteer-requests/{request_id}/join", headers=volunteer)
    client.post(f"/volunteer-requests/{request_id}/join", headers=other)

    client.delete(f"/volunteer-requests/{request_id}/join", headers=volunteer)

    assert joined_ids(test_session_factory, request_id) == [
        user_id(test_session_factory, "other@example.com")
    ]


def test_unknown_request_is_not_found(client, volunteer) -> None:
    assert client.post("/volunteer-requests/999999/join", headers=volunteer).status_code == 404
    assert client.delete("/volunteer-requests/999999/join", headers=volunteer).status_code == 404


def test_only_volunteer_masters_can_join_or_leave(client, test_session_factory) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help"})
    plain = make_volunteer(client, test_session_factory, "plain@example.com", False)
    client_user = register(client, "client@example.com", role="client")

    for headers in (plain, client_user):
        assert (
            client.post(f"/volunteer-requests/{request_id}/join", headers=headers).status_code
            == 403
        )
        assert (
            client.delete(f"/volunteer-requests/{request_id}/join", headers=headers).status_code
            == 403
        )
    assert client.post(f"/volunteer-requests/{request_id}/join").status_code == 401
    assert joined_ids(test_session_factory, request_id) == []
