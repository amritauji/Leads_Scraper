"""PostgreSQL connection manager using psycopg2."""

from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from app.config import DATABASE_URL as _CONFIG_URL


def get_connection(db_url: str | None = None):
    """Get a PostgreSQL connection.

    Args:
        db_url: Optional connection string. Falls back to DATABASE_URL env var.
    """
    url = db_url or _CONFIG_URL or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL not set. Add it to .env or pass db_url explicitly."
        )
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


@contextmanager
def db_transaction(conn):
    """Context manager for PostgreSQL transactions."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
