from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from app.exception_handlers import register_exception_handlers
from app.schemas.base import RequestSchema
from app.schemas.pagination import Page, PageParams


class ItemCreate(RequestSchema):
    name: str


def make_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/items")
    def create_item(item: ItemCreate) -> ItemCreate:
        return item

    @app.get("/items")
    def list_items(params: Annotated[PageParams, Query()]) -> Page[str]:
        return Page[str](items=[], total=0, limit=params.limit, offset=params.offset)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    return app


client = TestClient(make_app(), raise_server_exceptions=False)


def test_validation_error_has_common_format() -> None:
    response = client.post("/items", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["details"][0]["field"] == "body.name"


def test_request_schema_rejects_unknown_fields() -> None:
    response = client.post("/items", json={"name": "Ivan", "is_admin": True})

    assert response.status_code == 422
    fields = [detail["field"] for detail in response.json()["details"]]
    assert "body.is_admin" in fields


def test_strings_are_stripped() -> None:
    response = client.post("/items", json={"name": "  Ivan  "})

    assert response.status_code == 200
    assert response.json() == {"name": "Ivan"}


def test_not_found_has_common_format() -> None:
    response = client.get("/nope")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Not Found", "details": []}


def test_unhandled_error_hides_internal_details() -> None:
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "secret" not in response.text


def test_pagination_defaults() -> None:
    response = client.get("/items")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_pagination_limit_is_capped() -> None:
    response = client.get("/items", params={"limit": 500})

    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "query.limit"

def test_openapi_documents_error_schema() -> None:
    from app.main import app as main_app

    schema = TestClient(main_app).get("/openapi.json").json()

    assert "ErrorResponse" in schema["components"]["schemas"]
    assert "422" in schema["paths"]["/issues"]["get"]["responses"]