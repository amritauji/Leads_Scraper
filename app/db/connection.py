"""Database connection manager."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager

from app.db.schema import init_db

_default_db_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "output", "leads.db",
)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get a SQLite connection. Creates file and tables if needed."""
    path = db_path or _default_db_path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    return conn


@contextmanager
def db_transaction(conn: sqlite3.Connection):
    """Context manager for transactions."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
