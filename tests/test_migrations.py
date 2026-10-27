import os

import pytest
from alembic import command
from alembic.config import Config


def _alembic_config() -> Config:
    url = os.environ["DATABASE_URL"]
    # CI uses a plain postgresql:// URL; the app talks to Postgres via psycopg 3.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
def test_migrations_apply_and_match_models() -> None:
    config = _alembic_config()
    command.upgrade(config, "head")
    # Fails if the models and the migrations have drifted apart.
    command.check(config)
    command.downgrade(config, "base")
