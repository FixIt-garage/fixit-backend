from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.security import create_access_token
from app.models.catalog import Category, Service
from app.models.company import Company
from app.models.user import User, UserRole
from app.schemas.service_center import OpeningInterval, ServiceCenterUpdate
from app.services.service_center import get_working_status

KYIV_TZ = ZoneInfo("Europe/Kyiv")

OPENING_HOURS = {
    "monday": {"open": "09:00", "close": "19:00"},
    "tuesday": {"open": "09:00", "close": "19:00"},
    "wednesday": {"open": "09:00", "close": "19:00"},
    "thursday": {"open": "09:00", "close": "19:00"},
    "friday": {"open": "09:00", "close": "19:00"},
    "saturday": {"open": "10:00", "close": "16:00"},
    "sunday": None,
}


def create_user(db, email: str, role: UserRole) -> User:
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


def create_catalog(db):
    unique_id = uuid4().hex

    category = Category(
        name=f"Test service center category {unique_id}",
        slug=f"test-center-{unique_id}",
        name_uk="Тестова категорія",
    )
    db.add(category)
    db.flush()

    service = Service(
        category_id=category.id,
        name="Test repair service",
    )
    db.add(service)
    db.flush()

    return category, service


def create_service_center(db, owner: User) -> Company:
    category, service = create_catalog(db)

    company = Company(
        name="Test Service Center",
        type="service_center",
        owner_id=owner.id,
        address="Lviv, Test Street 1",
        latitude=Decimal("49.839700"),
        longitude=Decimal("24.029700"),
        phone="+380501234567",
        opening_hours=OPENING_HOURS,
        rating=Decimal("4.75"),
        reviews_count=12,
    )
    company.categories = [category]
    company.services = [service]

    db.add(company)
    db.flush()

    return company


def test_get_service_center_returns_full_profile(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        owner = create_user(
            db,
            "center-owner@example.com",
            UserRole.SERVICE_CENTER,
        )
        company = create_service_center(db, owner)
        public_id = company.public_id
        db.commit()

    response = client.get(f"/service-centers/{public_id}")

    assert response.status_code == 200
    body = response.json()

    assert body["public_id"] == public_id
    assert body["name"] == "Test Service Center"
    assert body["address"] == "Lviv, Test Street 1"
    assert body["phone"] == "+380501234567"
    assert body["location"] == {
        "latitude": 49.8397,
        "longitude": 24.0297,
    }
    assert body["rating"] == 4.75
    assert body["reviews_count"] == 12

    assert len(body["categories"]) == 1
    assert body["categories"][0]["name"].startswith("Test service center category ")
    assert len(body["services"]) == 1
    assert body["services"][0]["name"] == "Test repair service"

    assert body["opening_hours"]["monday"] == {
        "open": "09:00",
        "close": "19:00",
    }


def test_get_unknown_service_center_returns_404(
    client: TestClient,
) -> None:
    response = client.get("/service-centers/999999")

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (
            datetime(2026, 11, 16, 12, 0, tzinfo=KYIV_TZ),
            (True, "Відчинено до 19:00"),
        ),
        (
            datetime(2026, 11, 16, 8, 0, tzinfo=KYIV_TZ),
            (False, "Зачинено"),
        ),
        (
            datetime(2026, 11, 16, 19, 0, tzinfo=KYIV_TZ),
            (False, "Зачинено"),
        ),
        (
            datetime(2026, 11, 22, 12, 0, tzinfo=KYIV_TZ),
            (False, "Зачинено"),
        ),
    ],
)
def test_working_status_calculation(moment, expected) -> None:
    assert get_working_status(OPENING_HOURS, moment) == expected


def test_working_status_without_schedule() -> None:
    assert get_working_status(None) == (False, "Графік не вказано")


def test_opening_interval_validation() -> None:
    interval = OpeningInterval(open="09:00", close="19:00")

    assert interval.open == "09:00"
    assert interval.close == "19:00"

    with pytest.raises(ValidationError):
        OpeningInterval(open="19:00", close="09:00")


def test_service_center_update_preserves_unprovided_fields() -> None:
    data = ServiceCenterUpdate(name="Updated Center")

    changes = data.model_dump(exclude_unset=True, mode="json")

    assert changes == {"name": "Updated Center"}


def test_service_center_update_allows_empty_category_and_service_lists() -> None:
    data = ServiceCenterUpdate(
        category_ids=[],
        service_ids=[],
    )

    changes = data.model_dump(exclude_unset=True, mode="json")

    assert changes == {
        "category_ids": [],
        "service_ids": [],
    }


def test_service_center_update_rejects_null_category_ids() -> None:
    with pytest.raises(ValidationError):
        ServiceCenterUpdate(category_ids=None)


def test_owner_can_update_service_center(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        owner = create_user(
            db,
            "update-center-owner@example.com",
            UserRole.SERVICE_CENTER,
        )
        company = create_service_center(db, owner)
        token = create_access_token(str(owner.id))
        public_id = company.public_id
        category_id = company.categories[0].id
        service_id = company.services[0].id
        db.commit()

    response = client.patch(
        "/service-centers/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Updated Service Center",
            "category_ids": [category_id],
            "service_ids": [service_id],
            "opening_hours": OPENING_HOURS,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["public_id"] == public_id
    assert body["name"] == "Updated Service Center"
    assert body["categories"][0]["id"] == category_id
    assert body["services"][0]["id"] == service_id


def test_another_service_center_owner_cannot_update_center(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        owner = create_user(
            db,
            "original-center-owner@example.com",
            UserRole.SERVICE_CENTER,
        )
        other_owner = create_user(
            db,
            "other-center-owner@example.com",
            UserRole.SERVICE_CENTER,
        )
        create_service_center(db, owner)

        token = create_access_token(str(other_owner.id))
        db.commit()

    response = client.patch(
        "/service-centers/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Unauthorized update"},
    )

    assert response.status_code == 404


def test_user_with_wrong_role_cannot_update_service_center(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        client_user = create_user(
            db,
            "regular-client@example.com",
            UserRole.CLIENT,
        )
        token = create_access_token(str(client_user.id))
        db.commit()

    response = client.patch(
        "/service-centers/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Unauthorized update"},
    )

    assert response.status_code == 403


def test_owner_without_service_center_gets_404(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        owner = create_user(
            db,
            "owner-without-center@example.com",
            UserRole.SERVICE_CENTER,
        )
        token = create_access_token(str(owner.id))
        db.commit()

    response = client.patch(
        "/service-centers/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "New name"},
    )

    assert response.status_code == 404


def test_owner_with_multiple_centers_gets_409(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        owner = create_user(
            db,
            "multiple-centers-owner@example.com",
            UserRole.SERVICE_CENTER,
        )
        create_service_center(db, owner)
        create_service_center(db, owner)

        token = create_access_token(str(owner.id))
        db.commit()

    response = client.patch(
        "/service-centers/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Ambiguous update"},
    )

    assert response.status_code == 409


def test_partial_opening_hours_update_preserves_other_days(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        owner = create_user(
            db,
            "partial-hours-owner@example.com",
            UserRole.SERVICE_CENTER,
        )
        create_service_center(db, owner)
        token = create_access_token(str(owner.id))
        db.commit()

    response = client.patch(
        "/service-centers/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "opening_hours": {
                "monday": {
                    "open": "10:00",
                    "close": "18:00",
                }
            }
        },
    )

    assert response.status_code == 200

    hours = response.json()["opening_hours"]

    assert hours["monday"] == {
        "open": "10:00",
        "close": "18:00",
    }
    assert hours["tuesday"] == {
        "open": "09:00",
        "close": "19:00",
    }
    assert hours["saturday"] == {
        "open": "10:00",
        "close": "16:00",
    }


def test_owner_can_clear_categories_and_services(
    client: TestClient,
    test_session_factory,
) -> None:
    with test_session_factory() as db:
        owner = create_user(
            db,
            "clear-catalog-owner@example.com",
            UserRole.SERVICE_CENTER,
        )
        create_service_center(db, owner)
        token = create_access_token(str(owner.id))
        db.commit()

    response = client.patch(
        "/service-centers/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "category_ids": [],
            "service_ids": [],
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["categories"] == []
    assert body["services"] == []
