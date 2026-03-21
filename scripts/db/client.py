"""
scripts/db/client.py
Central PostgreSQL client — used by all scripts.
"""
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_cursor(row_factory=psycopg2.extras.RealDictCursor):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=row_factory) as cur:
            yield cur


def execute(sql: str, params=None):
    """Run a single statement, return rowcount."""
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def fetchall(sql: str, params=None) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetchone(sql: str, params=None) -> dict | None:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()
