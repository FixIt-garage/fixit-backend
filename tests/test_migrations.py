"""Migration round-trip tests.

Migrations never run against the database named in DATABASE_URL. That URL is only used to
reach the Postgres server and create throw-away databases. Each test drops exactly the
databases it created and nothing else. If a throw-away database cannot be created, the test
fails before any migration runs.
"""

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")

TEMP_DB_PREFIX = "fixit_migtest_"


def _server_url() -> URL:
    """Connection to the Postgres server, used only to create/drop throw-away databases."""
    # CI passes a plain postgresql:// URL; the app talks to Postgres via psycopg 3.
    return make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql+psycopg")


def _database_exists(name: str) -> bool:
    engine = create_engine(_server_url())
    try:
        with engine.connect() as conn:
            query = text("SELECT 1 FROM pg_database WHERE datname = :name")
            return conn.execute(query, {"name": name}).scalar() is not None
    finally:
        engine.dispose()


@contextmanager
def disposable_database() -> Iterator[URL]:
    """Create a uniquely named database, yield its URL, then drop only that database."""
    name = f"{TEMP_DB_PREFIX}{uuid.uuid4().hex[:12]}"
    admin = create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except SQLAlchemyError as exc:
        admin.dispose()
        pytest.fail(
            f"Cannot create a throw-away database, refusing to run migrations: {exc}",
            pytrace=False,
        )
    try:
        yield _server_url().set(database=name)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _alembic_config(url: URL) -> Config:
    config = Config("alembic.ini")
    # ConfigParser treats "%" as interpolation, so escape it (e.g. percent-encoded passwords).
    rendered = url.render_as_string(hide_password=False)
    config.set_main_option("sqlalchemy.url", rendered.replace("%", "%%"))
    return config


def _migration_round_trip(url: URL) -> None:
    config = _alembic_config(url)
    command.upgrade(config, "head")
    command.check(config)  # fails if the models and the migrations have drifted apart
    command.downgrade(config, "base")


def test_migrations_apply_and_match_models() -> None:
    with disposable_database() as url:
        temp_name = url.database
        _migration_round_trip(url)

    assert not _database_exists(temp_name)


def test_migration_round_trip_leaves_other_databases_untouched() -> None:
    # The control database is throw-away too: it has the app schema and one record.
    with disposable_database() as control_url:
        command.upgrade(_alembic_config(control_url), "head")
        control = create_engine(control_url)
        try:
            with control.begin() as conn:
                conn.execute(text("INSERT INTO categories (name) VALUES ('control')"))

            with disposable_database() as temp_url:
                temp_name = temp_url.database
                assert temp_name != control_url.database
                _migration_round_trip(temp_url)

            assert not _database_exists(temp_name)
            assert _database_exists(control_url.database)
            with control.connect() as conn:
                names = conn.execute(text("SELECT name FROM categories")).scalars().all()
            assert names == ["control"]
        finally:
            control.dispose()
