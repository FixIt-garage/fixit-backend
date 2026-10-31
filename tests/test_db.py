import os

import psycopg
import pytest
from sqlalchemy.engine import make_url


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
def test_db_connection():
    database_url = make_url(os.environ["DATABASE_URL"]).set(
        drivername="postgresql"
    )

    with psycopg.connect(database_url.render_as_string(hide_password=False)) as conn:
        assert conn.execute("SELECT 1").fetchone() == (1,)