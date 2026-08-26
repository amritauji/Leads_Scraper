"""Phase 4 schema migration: auth_user_id on users, reviewed_by on review_queue.

Run once to add Supabase Auth linkage and review actor tracking.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import psycopg2
from app.config import DATABASE_URL


def migrate():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # --- 1. Add auth_user_id to users ---
    print("  Adding auth_user_id to users...")
    try:
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_user_id UUID UNIQUE")
    except Exception:
        conn.rollback()
        conn.autocommit = True
        print("    auth_user_id column may already exist")

    # --- 2. Add reviewed_by, reviewed_at to review_queue ---
    print("  Adding reviewed_by, reviewed_at to review_queue...")
    try:
        cur.execute("ALTER TABLE review_queue ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES users(user_id) ON DELETE SET NULL")
    except Exception:
        conn.rollback()
        conn.autocommit = True
        print("    reviewed_by column may already exist")

    try:
        cur.execute("ALTER TABLE review_queue ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ")
    except Exception:
        conn.rollback()
        conn.autocommit = True
        print("    reviewed_at column may already exist")

    # --- 3. Indexes ---
    print("  Creating indexes...")
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_auth_user_id ON users(auth_user_id)")
    except Exception:
        pass
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rq_reviewed_by ON review_queue(reviewed_by)")
    except Exception:
        pass

    cur.close()
    conn.close()
    print("\n  Phase 4 schema migration complete.")


if __name__ == "__main__":
    migrate()
