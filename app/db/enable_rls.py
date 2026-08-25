"""Enable RLS on all Phase 2 tables with service-role-only policies.

Run this once to fix Supabase security linter warnings.
The backend connects via DATABASE_URL (pooler, postgres role) — this allows full access.
PostgREST/anon role is blocked by default when RLS is enabled with no matching policy.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import psycopg2
from app.config import get

TABLES = [
    "quality_results",
    "confidence_results",
    "lead_master",
    "duplicate_events",
    "review_queue",
]

def main():
    url = get("DATABASE_URL")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    for table in TABLES:
        print(f"  Enabling RLS on {table}...")
        cur.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

        policy_name = f"allow_service_role_{table}"
        cur.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE tablename = '{table}' AND policyname = '{policy_name}'
                ) THEN
                    CREATE POLICY {policy_name} ON {table}
                        FOR ALL
                        TO postgres
                        USING (true)
                        WITH CHECK (true);
                END IF;
            END
            $$;
        """)
        print(f"    Policy '{policy_name}' created (allows 'postgres' role full access)")

    cur.close()
    conn.close()
    print("\n  Done. All 5 tables now have RLS enabled.")
    print("  PostgREST/anon access blocked. Direct PostgreSQL access (pooler) allowed.")

if __name__ == "__main__":
    main()
