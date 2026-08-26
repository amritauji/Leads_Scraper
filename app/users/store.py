"""User store backed by PostgreSQL (Supabase)."""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from app.db.connection import get_connection
from app.models import AppUser


class UserStore:
    """PostgreSQL-backed User store."""

    def __init__(self, db_url: str | None = None):
        self._db_url = db_url

    def _conn(self):
        return get_connection(self._db_url)

    def add(self, user: AppUser) -> AppUser:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO users (user_id, auth_user_id, name, email, role, is_active, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (user_id) DO UPDATE SET
                        auth_user_id = EXCLUDED.auth_user_id,
                        name = EXCLUDED.name, email = EXCLUDED.email, role = EXCLUDED.role,
                        is_active = EXCLUDED.is_active, updated_at = EXCLUDED.updated_at""",
                    (user.user_id, user.auth_user_id, user.name, user.email, user.role,
                     user.is_active, user.created_at, user.updated_at),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return user

    def get_by_id(self, user_id: str) -> AppUser | None:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                return self._row_to_user(row) if row else None
        finally:
            conn.close()

    def get_by_auth_user_id(self, auth_user_id: str) -> AppUser | None:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE auth_user_id = %s", (auth_user_id,))
                row = cur.fetchone()
                return self._row_to_user(row) if row else None
        finally:
            conn.close()

    def get_by_email(self, email: str) -> AppUser | None:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                row = cur.fetchone()
                return self._row_to_user(row) if row else None
        finally:
            conn.close()

    def get_all(self, active_only: bool = False) -> list[AppUser]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if active_only:
                    cur.execute("SELECT * FROM users WHERE is_active = TRUE ORDER BY name")
                else:
                    cur.execute("SELECT * FROM users ORDER BY name")
                return [self._row_to_user(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def update(self, user_id: str, name: str | None = None, role: str | None = None,
               is_active: bool | None = None, auth_user_id: str | None = None) -> AppUser | None:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                fields = []
                params = []
                if name is not None:
                    fields.append("name = %s")
                    params.append(name)
                if role is not None:
                    fields.append("role = %s")
                    params.append(role)
                if is_active is not None:
                    fields.append("is_active = %s")
                    params.append(is_active)
                if auth_user_id is not None:
                    fields.append("auth_user_id = %s")
                    params.append(auth_user_id)
                if not fields:
                    return self.get_by_id(user_id)
                fields.append("updated_at = NOW()")
                params.append(user_id)
                cur.execute(
                    f"UPDATE users SET {', '.join(fields)} WHERE user_id = %s RETURNING *",
                    params,
                )
                row = cur.fetchone()
                conn.commit()
                return self._row_to_user(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def clear(self):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users")
            conn.commit()
        finally:
            conn.close()

    def _row_to_user(self, row: dict) -> AppUser:
        return AppUser(
            user_id=str(row["user_id"]),
            auth_user_id=str(row["auth_user_id"]) if row.get("auth_user_id") else None,
            name=row["name"],
            email=row["email"],
            role=row["role"],
            is_active=row["is_active"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
