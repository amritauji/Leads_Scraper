"""Phase 3 schema migration: Users, Assignment, Pipeline, Activities.

Run once to create the Phase 3 tables and extend lead_master.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import psycopg2
from app.config import DATABASE_URL


def migrate():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # --- 1. Create users table ---
    print("  Creating users table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'manager', 'bd')),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # --- 2. Extend lead_master ---
    print("  Extending lead_master...")

    alter_statements = [
        "ALTER TABLE lead_master ADD COLUMN IF NOT EXISTS assigned_to UUID REFERENCES users(user_id) ON DELETE SET NULL",
        "ALTER TABLE lead_master ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ",
        "ALTER TABLE lead_master ADD COLUMN IF NOT EXISTS assigned_by UUID REFERENCES users(user_id) ON DELETE SET NULL",
        "ALTER TABLE lead_master ADD COLUMN IF NOT EXISTS pipeline_stage TEXT NOT NULL DEFAULT 'new'",
        "ALTER TABLE lead_master ADD COLUMN IF NOT EXISTS pipeline_stage_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "ALTER TABLE lead_master ADD COLUMN IF NOT EXISTS pipeline_changed_by UUID REFERENCES users(user_id) ON DELETE SET NULL",
        "ALTER TABLE lead_master ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high'))",
        "ALTER TABLE lead_master ADD COLUMN IF NOT EXISTS next_action_at TIMESTAMPTZ",
        "ALTER TABLE lead_master ADD COLUMN IF NOT EXISTS next_action_type TEXT CHECK (next_action_type IN ('call', 'email', 'meeting', 'follow_up', 'other'))",
    ]

    for stmt in alter_statements:
        try:
            cur.execute(stmt)
        except psycopg2.errors.DuplicateColumn:
            conn.rollback()
            print(f"    Column already exists, skipping: {stmt.split('ADD COLUMN IF NOT EXISTS ')[1].split()[0]}")
            conn.autocommit = True

    # Extend status check constraint
    try:
        cur.execute("ALTER TABLE lead_master DROP CONSTRAINT IF EXISTS lead_master_status_check")
        cur.execute("ALTER TABLE lead_master ADD CONSTRAINT lead_master_status_check CHECK (status IN ('accepted', 'under_review', 'merged', 'archived'))")
    except Exception:
        conn.rollback()
        conn.autocommit = True

    # --- 3. Create lead_assignments ---
    print("  Creating lead_assignments table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lead_assignments (
            assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            master_id TEXT NOT NULL REFERENCES lead_master(master_id) ON DELETE CASCADE,
            assigned_to UUID NOT NULL REFERENCES users(user_id) ON DELETE SET NULL,
            assigned_by UUID NOT NULL REFERENCES users(user_id) ON DELETE SET NULL,
            action TEXT NOT NULL CHECK (action IN ('assigned', 'reassigned', 'unassigned')),
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # --- 4. Create lead_pipeline_history ---
    print("  Creating lead_pipeline_history table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lead_pipeline_history (
            transition_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            master_id TEXT NOT NULL REFERENCES lead_master(master_id) ON DELETE CASCADE,
            from_stage TEXT,
            to_stage TEXT NOT NULL,
            changed_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # --- 5. Create lead_activities ---
    print("  Creating lead_activities table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lead_activities (
            activity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            master_id TEXT NOT NULL REFERENCES lead_master(master_id) ON DELETE CASCADE,
            activity_type TEXT NOT NULL,
            performed_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
            title TEXT NOT NULL,
            description TEXT,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # --- 6. Indexes ---
    print("  Creating indexes...")
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
        "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_lm_assigned_to ON lead_master(assigned_to)",
        "CREATE INDEX IF NOT EXISTS idx_lm_pipeline_stage ON lead_master(pipeline_stage)",
        "CREATE INDEX IF NOT EXISTS idx_lm_priority ON lead_master(priority)",
        "CREATE INDEX IF NOT EXISTS idx_lm_next_action_at ON lead_master(next_action_at)",
        "CREATE INDEX IF NOT EXISTS idx_la_master_id ON lead_assignments(master_id)",
        "CREATE INDEX IF NOT EXISTS idx_la_assigned_to ON lead_assignments(assigned_to)",
        "CREATE INDEX IF NOT EXISTS idx_lph_master_id ON lead_pipeline_history(master_id)",
        "CREATE INDEX IF NOT EXISTS idx_lph_created_at ON lead_pipeline_history(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_lact_master_id ON lead_activities(master_id)",
        "CREATE INDEX IF NOT EXISTS idx_lact_activity_type ON lead_activities(activity_type)",
        "CREATE INDEX IF NOT EXISTS idx_lact_created_at ON lead_activities(created_at)",
    ]
    for idx in indexes:
        try:
            cur.execute(idx)
        except Exception:
            pass

    # --- 7. RLS ---
    print("  Enabling RLS on new tables...")
    for table in ["users", "lead_assignments", "lead_pipeline_history", "lead_activities"]:
        try:
            cur.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            cur.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies WHERE tablename = '{table}' AND policyname = 'allow_service_role_{table}'
                    ) THEN
                        CREATE POLICY allow_service_role_{table} ON {table}
                            FOR ALL TO postgres USING (true) WITH CHECK (true);
                    END IF;
                END
                $$;
            """)
        except Exception:
            pass

    cur.close()
    conn.close()
    print("\n  Phase 3 schema migration complete.")


if __name__ == "__main__":
    migrate()
