"""The mobile sign-up form still reads FastAPI's old ``detail`` field.

These tests keep that contract working until fixit-mobile moves to code/message/details.
"""

from fastapi.testclient import TestClient

USER = {
    "email": "compat@example.com",
    "password": "TestPassword123!",
    "first_name": "Test",
    "last_name": "User",
    "phone": "+380501234567",
}


def test_duplicate_email_409_has_new_and_legacy_format(client: TestClient) -> None:
    assert client.post("/auth/register", json=USER).status_code == 201

    response = client.post("/auth/register", json={**USER, "phone": "+380507654321"})

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "conflict"
    assert "email" in body["message"]
    assert "email" in body["detail"]


def test_duplicate_phone_409_has_new_and_legacy_format(client: TestClient) -> None:
    assert client.post("/auth/register", json=USER).status_code == 201

    response = client.post("/auth/register", json={**USER, "email": "other@example.com"})

    assert response.status_code == 409
    assert "phone" in response.json()["message"]
    assert "phone" in response.json()["detail"]


def test_invalid_register_422_has_new_and_legacy_field_paths(client: TestClient) -> None:
    response = client.post("/auth/register", json={**USER, "email": "not-an-email"})

    assert response.status_code == 422
    body = response.json()
    assert "body.email" in [detail["field"] for detail in body["details"]]
    assert "email" in [item["loc"][-1] for item in body["detail"]]
    assert USER["password"] not in response.text