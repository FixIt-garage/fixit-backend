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
                before = (
                    conn.execute(text("SELECT name FROM categories ORDER BY id")).scalars().all()
                )

            with disposable_database() as temp_url:
                temp_name = temp_url.database
                assert temp_name != control_url.database
                _migration_round_trip(temp_url)

            assert not _database_exists(temp_name)
            assert _database_exists(control_url.database)
            with control.connect() as conn:
                names = (
                    conn.execute(text("SELECT name FROM categories ORDER BY id")).scalars().all()
                )
            # The migration of the other database must not change this one.
            assert names == before
            assert "control" in names
        finally:
            control.dispose()


PRE_SEED_REVISION = "e3b46f671fc0"


@requires_db
def test_seed_migration_keeps_ids_and_fills_categories_api() -> None:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.db import get_db
    from app.main import app

    with disposable_database() as url:
        _assert_connected_to(url)
        config = _alembic_config(url)
        command.upgrade(config, PRE_SEED_REVISION)
        engine = create_engine(url)
        try:
            # Rows as the old app/seed.py created them: only `name`, no slug / name_uk.
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO categories (name) VALUES ('Електрика'), ('Сантехніка')")
                )
                legacy = dict(conn.execute(text("SELECT name, id FROM categories")).all())
                conn.execute(
                    text("INSERT INTO services (category_id, name) VALUES (:id, 'Заміна розетки')"),
                    {"id": legacy["Електрика"]},
                )

            command.upgrade(config, "head")

            factory = sessionmaker(bind=engine)

            def override_get_db():
                with factory() as db:
                    yield db

            app.dependency_overrides[get_db] = override_get_db
            try:
                items = TestClient(app).get("/categories").json()
            finally:
                app.dependency_overrides.clear()

            by_slug = {item["slug"]: item for item in items}
            assert len(items) == 7
            assert all(item["slug"] and item["name_uk"] for item in items)
            # Existing categories keep their ids, so services stay linked.
            assert by_slug["electrics"]["id"] == legacy["Електрика"]
            assert by_slug["plumbing"]["id"] == legacy["Сантехніка"]
            # Sub-categories point to their parent.
            assert by_slug["washing-machines"]["parent_id"] == by_slug["appliances"]["id"]
            assert by_slug["refrigerators"]["parent_id"] == by_slug["appliances"]["id"]
            assert by_slug["appliances"]["parent_id"] is None
            # The API result is ordered by sort_order.
            orders = [item["sort_order"] for item in items]
            assert orders == sorted(orders)
            with engine.connect() as conn:
                linked = (
                    conn.execute(
                        text(
                            "SELECT c.slug FROM services s "
                            "JOIN categories c ON c.id = s.category_id"
                        )
                    )
                    .scalars()
                    .all()
                )
            assert linked == ["electrics"]
        finally:
            engine.dispose()


def _insert_legacy_categories(engine, names: list[str]) -> dict[str, int]:
    """Insert categories as the old app/seed.py did: only `name`, no slug or name_uk."""
    with engine.begin() as conn:
        for name in names:
            conn.execute(text("INSERT INTO categories (name) VALUES (:name)"), {"name": name})
        return dict(conn.execute(text("SELECT name, id FROM categories")).all())


@requires_db
def test_seed_downgrade_keeps_existing_categories() -> None:
    with disposable_database() as url:
        _assert_connected_to(url)
        config = _alembic_config(url)
        command.upgrade(config, PRE_SEED_REVISION)
        engine = create_engine(url)
        try:
            legacy = _insert_legacy_categories(engine, ["Електрика", "Сантехніка"])
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO services (category_id, name) VALUES (:id, 'Заміна розетки')"),
                    {"id": legacy["Електрика"]},
                )

            command.upgrade(config, "head")
            command.downgrade(config, PRE_SEED_REVISION)

            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT id, name, slug FROM categories "
                        "WHERE name IN ('Електрика', 'Сантехніка')"
                    )
                ).all()
                linked = conn.execute(text("SELECT category_id FROM services")).scalars().all()
            # Both pre-existing rows keep their id, with or without services.
            assert {row.name: row.id for row in rows} == legacy
            assert all(row.slug is None for row in rows)
            assert linked == [legacy["Електрика"]]
        finally:
            engine.dispose()


@requires_db
def test_seed_downgrade_works_with_extra_child_categories() -> None:
    with disposable_database() as url:
        _assert_connected_to(url)
        config = _alembic_config(url)
        command.upgrade(config, "head")
        engine = create_engine(url)
        try:
            with engine.begin() as conn:
                ids = dict(conn.execute(text("SELECT slug, id FROM categories")).all())
                conn.execute(
                    text(
                        "INSERT INTO categories (name, slug, name_uk, parent_id, sort_order) "
                        "VALUES ('Духовки', 'ovens', 'Духовки', :appliances, 3), "
                        "('Фільтри', 'filters', 'Фільтри', :washing, 1)"
                    ),
                    {"appliances": ids["appliances"], "washing": ids["washing-machines"]},
                )

            # Children outside the seed must not make the rollback fail on ON DELETE RESTRICT.
            command.downgrade(config, PRE_SEED_REVISION)

            with engine.connect() as conn:
                by_name = dict(conn.execute(text("SELECT name, id FROM categories")).all())
                parents = dict(
                    conn.execute(
                        text("SELECT name, parent_id FROM categories WHERE parent_id IS NOT NULL")
                    ).all()
                )
            assert parents == {
                "Духовки": by_name["Побутова техніка"],
                "Фільтри": by_name["Пральні машини"],
            }
        finally:
            engine.dispose()


@requires_db
def test_user_profile_migration_fills_public_id_for_existing_users() -> None:
    with disposable_database() as url:
        _assert_connected_to(url)
        config = _alembic_config(url)
        command.upgrade(config, "968fca11f4b9")
        engine = create_engine(url)
        try:
            with engine.begin() as conn:
                for email in ("first@example.com", "second@example.com"):
                    conn.execute(
                        text(
                            "INSERT INTO users (email, password_hash, first_name, last_name) "
                            "VALUES (:email, 'hash', 'Test', 'User')"
                        ),
                        {"email": email},
                    )

            command.upgrade(config, "head")

            with engine.connect() as conn:
                ids = conn.execute(text("SELECT public_id FROM users ORDER BY id")).scalars().all()
            assert len(ids) == 2
            assert len(set(ids)) == 2
            assert min(ids) >= 1000

            # A user created after the migration gets the next number automatically.
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO users (email, password_hash, first_name, last_name) "
                        "VALUES ('third@example.com', 'hash', 'Test', 'User')"
                    )
                )
                last = conn.execute(
                    text("SELECT public_id FROM users WHERE email = 'third@example.com'")
                ).scalar_one()
            assert last > max(ids)
        finally:
            engine.dispose()
