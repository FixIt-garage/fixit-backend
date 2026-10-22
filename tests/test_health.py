from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    
def test_health_returns_ok_when_db_is_up() -> None:
    app.dependency_overrides[get_db] = lambda: MagicMock()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}

    app.dependency_overrides.clear()
