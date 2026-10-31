import os
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import jwt
import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core.dependencies import require_role
from app.db import get_db
from app.main import app
from app.models.user import User, UserRole
from app.routers import auth as auth_module


@pytest.fixture
def test_session_factory():
    """Create an isolated PostgreSQL database for authentication tests."""
    server_url = make_url(os.environ["DATABASE_URL"]).set(
        drivername="postgresql+psycopg"
    )

    database_name = f"fixit_authtest_{uuid.uuid4().hex[:12]}"

    admin_engine = create_engine(
        server_url,
        isolation_level="AUTOCOMMIT",
    )
    test_engine = None

    try:
        with admin_engine.connect() as connection:
            connection.execute(
                text(f'CREATE DATABASE "{database_name}"')
            )

        test_url = server_url.difference_update_query(
            ["dbname"]
        ).set(database=database_name)

        test_engine = create_engine(test_url)

        alembic_config = Config("alembic.ini")
        rendered_url = test_url.render_as_string(hide_password=False)
        alembic_config.set_main_option(
            "sqlalchemy.url",
            rendered_url.replace("%", "%%"),
        )

        command.upgrade(alembic_config, "head")

        yield sessionmaker(bind=test_engine, autoflush=False)

    finally:
        if test_engine is not None:
            test_engine.dispose()

        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'
                )
            )

        admin_engine.dispose()


@pytest.fixture
def client(test_session_factory) -> Iterator[TestClient]:
    """Create a test client using the isolated PostgreSQL database."""

    def override_get_db():
        db = test_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def register_user(client: TestClient) -> dict:
    """Register a test user and return the response data."""
    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User",
        },
    )

    assert response.status_code == 201
    return response.json()


def test_register_and_get_me(client: TestClient) -> None:
    tokens = register_user(client)

    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {tokens['access_token']}"
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
    assert response.json()["first_name"] == "Test"
    assert response.json()["role"] == "client"

def test_invalid_access_token_rejected(client: TestClient) -> None:
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_expired_access_token_rejected(client: TestClient) -> None:
    expired_token = jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401

def test_register_duplicate_email(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "AnotherPassword123!",
            "first_name": "Another",
            "last_name": "User",
        },
    )

    assert response.status_code == 409

def test_concurrent_registration_same_email(
    client: TestClient,
    test_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only one concurrent registration with the same email succeeds."""
    barrier = Barrier(2)
    original_hash_password = auth_module.hash_password

    def synchronized_hash_password(password: str) -> str:
        barrier.wait(timeout=10)
        return original_hash_password(password)

    monkeypatch.setattr(
        auth_module,
        "hash_password",
        synchronized_hash_password,
    )

    payload = {
        "email": "concurrent@example.com",
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "User",
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                client.post,
                "/auth/register",
                json=payload,
            )
            for _ in range(2)
        ]

        responses = [future.result(timeout=30) for future in futures]

    assert sorted(response.status_code for response in responses) == [201, 409]

    with test_session_factory() as db:
        user_count = db.scalar(
            select(func.count()).select_from(User).where(
                User.email == "concurrent@example.com"
            )
        )

    assert user_count == 1

def test_login(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["refresh_token"]


def test_login_invalid_password(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401


def test_refresh_rotates_tokens(client: TestClient) -> None:
    tokens = register_user(client)

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert response.status_code == 200

    new_tokens = response.json()

    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    old_token_response = client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert old_token_response.status_code == 401


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    tokens = register_user(client)

    response = client.post(
        "/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"

    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert refresh_response.status_code == 401


def test_token_check(client: TestClient) -> None:
    tokens = register_user(client)

    response = client.get(
        "/auth/token-check",
        headers={
            "Authorization": f"Bearer {tokens['access_token']}"
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Access token is valid"

def test_require_role_rejects_wrong_role() -> None:
    role_checker = require_role(UserRole.MASTER)

    client_user = User(
        email="client@example.com",
        password_hash="hashed-password",
        first_name="Test",
        last_name="Client",
        role=UserRole.CLIENT,
    )

    with pytest.raises(HTTPException) as exc_info:
        role_checker(current_user=client_user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Insufficient permissions"
