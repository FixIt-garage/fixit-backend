from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.user import User

CAPITALS = "Dupe@example.com"
LOWER = "dupe@example.com"
PASSWORD_A = "PasswordOfA1!"
PASSWORD_B = "PasswordOfB1!"


def register(client: TestClient, email: str, password: str, expected: int = 201) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Test",
            "last_name": "User",
        },
    )

    assert response.status_code == expected


def login(client: TestClient, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


def make_legacy_pair(client: TestClient, test_session_factory) -> tuple[int, int]:
    """Two accounts whose emails differ only by case, as the old unique index allowed."""
    register(client, "a@example.com", PASSWORD_A)
    register(client, "b@example.com", PASSWORD_B)
    with test_session_factory() as db:
        first = db.scalar(select(User).where(User.email == "a@example.com"))
        second = db.scalar(select(User).where(User.email == "b@example.com"))
        ids = (first.id, second.id)
        first.email = CAPITALS
        second.email = LOWER
        db.commit()
    return ids


def account_id(client: TestClient, response) -> int:
    token = response.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    return me.json()["id"]


def test_each_legacy_account_can_still_log_in(client: TestClient, test_session_factory) -> None:
    first_id, second_id = make_legacy_pair(client, test_session_factory)

    first = login(client, CAPITALS, PASSWORD_A)
    second = login(client, LOWER, PASSWORD_B)

    assert first.status_code == 200
    assert second.status_code == 200
    assert account_id(client, first) == first_id
    assert account_id(client, second) == second_id


def test_ambiguous_spelling_is_not_guessed(client: TestClient, test_session_factory) -> None:
    make_legacy_pair(client, test_session_factory)

    assert login(client, "DUPE@example.com", PASSWORD_A).status_code == 401
    assert login(client, "DUPE@example.com", PASSWORD_B).status_code == 401


def test_password_of_the_other_account_is_rejected(
    client: TestClient, test_session_factory
) -> None:
    make_legacy_pair(client, test_session_factory)

    assert login(client, CAPITALS, PASSWORD_B).status_code == 401
    assert login(client, LOWER, PASSWORD_A).status_code == 401


def test_both_legacy_accounts_stay_untouched(client: TestClient, test_session_factory) -> None:
    make_legacy_pair(client, test_session_factory)

    login(client, "DUPE@example.com", PASSWORD_A)

    with test_session_factory() as db:
        emails = sorted(db.scalars(select(User.email)))
    assert emails == [CAPITALS, LOWER]


def test_registering_a_conflicting_spelling_is_a_duplicate(
    client: TestClient, test_session_factory
) -> None:
    make_legacy_pair(client, test_session_factory)

    register(client, "DUPE@EXAMPLE.COM", "PasswordOfC1!", expected=409)
