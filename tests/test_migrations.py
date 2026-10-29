"""Migration round-trip tests.

Migrations never run against the database named in DATABASE_URL. That URL is only used to
reach the Postgres server and create throw-away databases. Each test drops exactly the
databases it created and nothing else. If a throw-away database cannot be created, or a
connection does not land in it, the test fails before any migration runs.
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

requires_db = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")

TEMP_DB_PREFIX = "fixit_migtest_"


def _server_url() -> URL:
    """Connection to the Postgres server, used only to create/drop throw-away databases."""
    # CI passes a plain postgresql:// URL; the app talks to Postgres via psycopg 3.
    return make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql+psycopg")


def _database_url(base: URL, name: str) -> URL:
    """URL of database `name` on the same server as `base`.

    A `dbname` query parameter would override the database from the URL path (the psycopg
    dialect merges query parameters into the connect args), so it is removed.
    """
    return base.difference_update_query(["dbname"]).set(database=name)


def _assert_connected_to(url: URL) -> None:
    """Fail before any migration if a connection to `url` lands in another database."""
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            actual = conn.execute(text("SELECT current_database()")).scalar()
    finally:
        engine.dispose()
    if actual != url.database:
        pytest.fail(
            f"Connected to {actual!r} instead of {url.database!r}, refusing to run migrations",
            pytrace=False,
        )


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
        yield _database_url(_server_url(), name)
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
    _assert_connected_to(url)
    config = _alembic_config(url)
    command.upgrade(config, "head")
    command.check(config)  # fails if the models and the migrations have drifted apart
    command.downgrade(config, "base")


def test_database_url_ignores_dbname_query_parameter() -> None:
    base = make_url("postgresql+psycopg://user:pw@localhost/fixit?dbname=fixit&sslmode=disable")
    url = _database_url(base, "fixit_migtest_x")

    # What the driver would actually receive, without connecting to a database.
    _, connect_kwargs = create_engine(url).dialect.create_connect_args(url)

    assert connect_kwargs["dbname"] == "fixit_migtest_x"
    assert connect_kwargs["sslmode"] == "disable"  # other query parameters are kept


@requires_db
def test_migrations_apply_and_match_models() -> None:
    with disposable_database() as url:
        temp_name = url.database
        _migration_round_trip(url)

    assert not _database_exists(temp_name)


@requires_db
def test_migration_round_trip_leaves_other_databases_untouched() -> None:
    # The control database is throw-away too: it has the app schema and one record.
    with disposable_database() as control_url:
        _assert_connected_to(control_url)
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
