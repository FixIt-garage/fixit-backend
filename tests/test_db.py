import os

import psycopg
import pytest


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
def test_db_connection():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        assert conn.execute("SELECT 1").fetchone() == (1,)