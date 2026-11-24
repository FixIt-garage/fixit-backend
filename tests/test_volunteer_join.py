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


def test_only_volunteer_masters_can_join_but_any_master_can_leave(
    client, test_session_factory
) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help"})
    plain = make_volunteer(client, test_session_factory, "plain@example.com", False)
    client_user = register(client, "client@example.com", role="client")
    join_url = f"/volunteer-requests/{request_id}/join"

    for headers in (plain, client_user):
        assert client.post(join_url, headers=headers).status_code == 403
    assert client.delete(join_url, headers=client_user).status_code == 403
    # A master without the volunteer mode may leave, but he has not joined anything here.
    assert client.delete(join_url, headers=plain).status_code == 404
    assert client.post(join_url).status_code == 401
    assert client.delete(join_url).status_code == 401
    assert joined_ids(test_session_factory, request_id) == []


def test_master_can_leave_after_turning_volunteer_mode_off(
    client, test_session_factory, volunteer
) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help", "needed": 1})
    client.post(f"/volunteer-requests/{request_id}/join", headers=volunteer)
    turned_off = client.patch(
        "/masters/me/volunteer", json={"is_volunteer": False}, headers=volunteer
    )

    leave = client.delete(f"/volunteer-requests/{request_id}/join", headers=volunteer)

    assert turned_off.status_code == 200
    assert leave.status_code == 204
    assert joined_ids(test_session_factory, request_id) == []


def test_after_turning_volunteer_mode_off_the_requests_stay_closed(
    client, test_session_factory, volunteer
) -> None:
    [request_id] = seed_requests(test_session_factory, {"title": "Help"})
    client.patch("/masters/me/volunteer", json={"is_volunteer": False}, headers=volunteer)

    assert client.get("/volunteer-requests", headers=volunteer).status_code == 403
    assert (
        client.post(f"/volunteer-requests/{request_id}/join", headers=volunteer).status_code == 403
    )


def test_two_masters_racing_for_the_last_place(client, test_session_factory, monkeypatch) -> None:
    import threading
    import time

    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import volunteer as volunteer_service

    first = make_volunteer(client, test_session_factory, "first@example.com")
    second = make_volunteer(client, test_session_factory, "second@example.com")
    [request_id] = seed_requests(test_session_factory, {"title": "Help", "needed": 1})

    original = volunteer_service._joined_counts

    def slow_counts(db, request_ids):
        counted = original(db, request_ids)
        time.sleep(1.0)  # a window between counting the places and taking one
        return counted

    monkeypatch.setattr(volunteer_service, "_joined_counts", slow_counts)
    results: dict[str, int] = {}

    def join(name: str, headers: dict[str, str], delay: float) -> None:
        time.sleep(delay)
        with TestClient(app) as thread_client:
            response = thread_client.post(f"/volunteer-requests/{request_id}/join", headers=headers)
        results[name] = response.status_code

    threads = [
        threading.Thread(target=join, args=("first", first, 0.0)),
        threading.Thread(target=join, args=("second", second, 0.3)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(results.values()) == [200, 409]
    assert len(joined_ids(test_session_factory, request_id)) == 1
