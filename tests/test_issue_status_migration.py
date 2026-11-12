import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

requires_db = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")

BEFORE = "3b7e1c4d9a52"
AFTER = "a91c4e7d2b36"
OLD_TO_NEW = {
    "OPEN": "sent",
    "IN_PROGRESS": "in_progress",
    "RESOLVED": "done",
    "CLOSED": "cancelled",
}


def _alembic_config(url) -> Config:
    config = Config("alembic.ini")
    rendered = url.render_as_string(hide_password=False)
    config.set_main_option("sqlalchemy.url", rendered.replace("%", "%%"))
    return config


def _statuses(engine) -> dict[str, str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT title, CAST(status AS text) FROM issues")).all()
    return {title: status for title, status in rows}


@requires_db
def test_status_migration_converts_existing_issues_and_back() -> None:
    server_url = make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql+psycopg")
    name = f"fixit_migtest_{uuid.uuid4().hex[:12]}"
    admin = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    engine = None
    try:
        url = server_url.difference_update_query(["dbname"]).set(database=name)
        config = _alembic_config(url)
        command.upgrade(config, BEFORE)

        engine = create_engine(url)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (email, password_hash, first_name, last_name) "
                    "VALUES ('m@example.com', 'x', 'Test', 'User')"
                )
            )
            owner_id = conn.execute(text("SELECT id FROM users")).scalar_one()
            category_id = conn.execute(text("SELECT id FROM categories LIMIT 1")).scalar_one()
            for old_status in OLD_TO_NEW:
                conn.execute(
                    text(
                        "INSERT INTO issues (title, description, category_id, status, "
                        "owner_id, created_at, updated_at) "
                        "VALUES (:title, 'd', :category_id, CAST(:status AS issuestatus), "
                        ":owner_id, now(), now())"
                    ),
                    {
                        "title": old_status,
                        "category_id": category_id,
                        "status": old_status,
                        "owner_id": owner_id,
                    },
                )

        command.upgrade(config, AFTER)
        assert _statuses(engine) == OLD_TO_NEW

        command.downgrade(config, BEFORE)
        assert _statuses(engine) == {old: old for old in OLD_TO_NEW}
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()