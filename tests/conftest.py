"""Shared fixtures: an isolated PostgreSQL database and a TestClient bound to it."""

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.db import get_db
from app.main import app


@pytest.fixture
def test_session_factory():
    """Create an isolated PostgreSQL database with all migrations applied."""
    server_url = make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql+psycopg")
    database_name = f"fixit_apitest_{uuid.uuid4().hex[:12]}"

    admin_engine = create_engine(server_url, isolation_level="AUTOCOMMIT")
    test_engine = None

    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))

        test_url = server_url.difference_update_query(["dbname"]).set(database=database_name)
        test_engine = create_engine(test_url)

        alembic_config = Config("alembic.ini")
        rendered_url = test_url.render_as_string(hide_password=False)
        alembic_config.set_main_option("sqlalchemy.url", rendered_url.replace("%", "%%"))
        command.upgrade(alembic_config, "head")

        yield sessionmaker(bind=test_engine, autoflush=False)
    finally:
        if test_engine is not None:
            test_engine.dispose()

        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))

        admin_engine.dispose()


@pytest.fixture
def client(test_session_factory) -> Iterator[TestClient]:
    """Create a test client that uses the isolated database."""

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
