from decimal import Decimal
from uuid import uuid4

from app.models.catalog import Category, Service
from app.models.company import Company
from app.models.master import Master
from app.models.user import User, UserRole


def create_category(db):
    unique_id = uuid4().hex

    category = Category(
        name=f"Electrical repair {unique_id}",
        slug=f"electrical-{unique_id}",
        name_uk="Електрика",
    )
    db.add(category)
    db.flush()

    service = Service(
        category_id=category.id,
        name="Electrical wiring repair",
    )
    db.add(service)
    db.flush()

    return category, service


def create_master(
    db,
    category,
    service,
    *,
    email,
    city="Lviv",
    rating="4.50",
    complete=True,
):
    user = User(
        email=email,
        password_hash="not-used-in-tests",
        first_name="Test",
        last_name="Master",
        role=UserRole.MASTER,
        city=city,
    )
    db.add(user)
    db.flush()

    master = Master(
        user_id=user.id,
        skills_description="Electrical wiring and repair",
        rating=Decimal(rating),
        reviews_count=5,
        experience_years=5 if complete else None,
        call_out_price=Decimal("500") if complete else None,
        schedule="Mon-Fri 9-18" if complete else None,
    )
    master.categories = [category]
    master.services = [service]

    db.add(master)
    db.flush()

    return master


def create_service_center(
    db,
    category,
    service,
    *,
    name,
    city="Lviv",
    rating="4.50",
):
    company = Company(
        name=name,
        type="service_center",
        address="Test Street 1",
        city=city,
        rating=Decimal(rating),
        reviews_count=5,
    )
    company.categories = [category]
    company.services = [service]

    db.add(company)
    db.flush()

    return company


def test_search_masters_filters_sorting_and_pagination(
    client,
    test_session_factory,
):
    with test_session_factory() as db:
        category, service = create_category(db)

        create_master(
            db,
            category,
            service,
            email="master-search-1@example.com",
            rating="4.20",
        )
        create_master(
            db,
            category,
            service,
            email="master-search-2@example.com",
            rating="4.90",
        )
        create_master(
            db,
            category,
            service,
            email="master-search-3@example.com",
            rating="4.50",
        )

        # Неповний профіль не повинен потрапити до результатів.
        create_master(
            db,
            category,
            service,
            email="master-search-incomplete@example.com",
            rating="5.00",
            complete=False,
        )

        category_id = category.id
        db.commit()

    response = client.get(
        "/search/masters",
        params={
            "city": "Lviv",
            "category_id": category_id,
            "sort": "rating",
            "limit": 2,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2
    assert [item["rating"] for item in body["items"]] == [4.9, 4.5]
    assert "contacts" not in body["items"][0]
    assert "phone" not in body["items"][0]

    next_page = client.get(
        "/search/masters",
        params={
            "city": "Lviv",
            "category_id": category_id,
            "limit": 2,
            "offset": 2,
        },
    )

    assert next_page.status_code == 200
    next_body = next_page.json()

    assert next_body["total"] == 3
    assert len(next_body["items"]) == 1
    assert next_body["items"][0]["rating"] == 4.2


def test_search_masters_by_text(
    client,
    test_session_factory,
):
    with test_session_factory() as db:
        category, service = create_category(db)

        create_master(
            db,
            category,
            service,
            email="master-search-text@example.com",
        )
        db.commit()

    response = client.get(
        "/search/masters",
        params={"q": "Electrical wiring"},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_search_masters_returns_empty_result(client):
    response = client.get(
        "/search/masters",
        params={"city": "Nonexistent city"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }


def test_search_service_centers_filters_sorting_and_pagination(
    client,
    test_session_factory,
):
    with test_session_factory() as db:
        category, service = create_category(db)

        create_service_center(
            db,
            category,
            service,
            name="Center One",
            rating="4.20",
        )
        create_service_center(
            db,
            category,
            service,
            name="Center Two",
            rating="4.90",
        )
        create_service_center(
            db,
            category,
            service,
            name="Center Three",
            rating="4.50",
        )
        create_service_center(
            db,
            category,
            service,
            name="Center Other City",
            city="Kyiv",
            rating="5.00",
        )

        category_id = category.id
        db.commit()

    response = client.get(
        "/search/service-centers",
        params={
            "city": "Lviv",
            "category_id": category_id,
            "sort": "rating",
            "limit": 2,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2
    assert [item["rating"] for item in body["items"]] == [4.9, 4.5]

    assert body["items"][0]["address"] == "Test Street 1"
    assert body["items"][0]["city"] == "Lviv"
    assert "is_open" in body["items"][0]

    next_page = client.get(
        "/search/service-centers",
        params={
            "city": "Lviv",
            "category_id": category_id,
            "limit": 2,
            "offset": 2,
        },
    )

    assert next_page.status_code == 200
    next_body = next_page.json()

    assert next_body["total"] == 3
    assert len(next_body["items"]) == 1
    assert next_body["items"][0]["rating"] == 4.2


def test_search_service_centers_by_text(
    client,
    test_session_factory,
):
    with test_session_factory() as db:
        category, service = create_category(db)

        create_service_center(
            db,
            category,
            service,
            name="Electrical Center",
        )
        db.commit()

    response = client.get(
        "/search/service-centers",
        params={"q": "Electrical wiring"},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_search_service_centers_returns_empty_result(client):
    response = client.get(
        "/search/service-centers",
        params={"city": "Nonexistent city"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }
