import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Category
from app.models.base import Base


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_get_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    with session_factory() as db:
        appliances = Category(
            name="appliances", slug="appliances", name_uk="Побутова техніка", sort_order=2
        )
        db.add_all(
            [
                appliances,
                Category(name="electrics", slug="electrics", name_uk="Електрика", sort_order=1),
            ]
        )
        db.flush()
        db.add(
            Category(
                name="washing-machines",
                slug="washing-machines",
                name_uk="Пральні машини",
                parent_id=appliances.id,
                sort_order=3,
            )
        )
        db.commit()

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_is_public_and_cached(client):
    response = client.get("/categories")
    assert response.status_code == 200
    assert "max-age" in response.headers["cache-control"]


def test_list_is_ordered_by_sort_order(client):
    slugs = [c["slug"] for c in client.get("/categories").json()]
    assert slugs == ["electrics", "appliances", "washing-machines"]


def test_subcategory_has_parent(client):
    items = {c["slug"]: c for c in client.get("/categories").json()}
    assert items["washing-machines"]["parent_id"] == items["appliances"]["id"]
    assert items["appliances"]["parent_id"] is None
