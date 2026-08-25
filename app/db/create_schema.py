"""Create all Phase 2 tables in Supabase PostgreSQL."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.config import get
import psycopg2

SCHEMA_SQL = """
-- ============================================================================
-- Phase 2 Schema: Data Quality -> Confidence -> Review -> Lead Master
-- ============================================================================

-- 1. quality_results
CREATE TABLE IF NOT EXISTS quality_results (
    quality_result_id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL,
    research_job_id TEXT,
    original_lead JSONB NOT NULL DEFAULT '{}',
    cleaned_lead JSONB NOT NULL DEFAULT '{}',
    validation_results JSONB NOT NULL DEFAULT '[]',
    duplicate_result JSONB NOT NULL DEFAULT '{}',
    issues JSONB NOT NULL DEFAULT '[]',
    conflicts JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quality_results_lead_id ON quality_results (lead_id);

-- 2. confidence_results
CREATE TABLE IF NOT EXISTS confidence_results (
    confidence_result_id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL,
    research_job_id TEXT,
    quality_result_id TEXT REFERENCES quality_results(quality_result_id) ON DELETE SET NULL,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    level TEXT NOT NULL CHECK (level IN ('high', 'medium', 'low')),
    positive_factors JSONB NOT NULL DEFAULT '[]',
    negative_factors JSONB NOT NULL DEFAULT '[]',
    conflicts JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_confidence_results_lead_id ON confidence_results (lead_id);
CREATE INDEX IF NOT EXISTS idx_confidence_results_quality_result_id ON confidence_results (quality_result_id);

-- 3. lead_master
CREATE TABLE IF NOT EXISTS lead_master (
    master_id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL,
    research_job_id TEXT,
    company_name TEXT,
    website TEXT,
    industry TEXT,
    category TEXT,
    segment TEXT,
    founded TEXT,
    revenue TEXT,
    city_country TEXT,
    ceo_founder_name TEXT,
    ceo_linkedin TEXT,
    marketing_head_name TEXT,
    marketing_head_linkedin TEXT,
    contact_email TEXT,
    confidence_score INTEGER,
    confidence_level TEXT,
    confidence_result_id TEXT REFERENCES confidence_results(confidence_result_id) ON DELETE SET NULL,
    quality_result_id TEXT REFERENCES quality_results(quality_result_id) ON DELETE SET NULL,
    data_quality_issues JSONB NOT NULL DEFAULT '[]',
    evidence_refs JSONB NOT NULL DEFAULT '[]',
    raw_evidence_refs JSONB NOT NULL DEFAULT '[]',
    review_id TEXT,
    source_lead_json JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'accepted' CHECK (status IN ('accepted', 'under_review', 'merged')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lead_master_company_name ON lead_master (company_name);
CREATE INDEX IF NOT EXISTS idx_lead_master_website ON lead_master (website);
CREATE INDEX IF NOT EXISTS idx_lead_master_contact_email ON lead_master (contact_email);
CREATE INDEX IF NOT EXISTS idx_lead_master_confidence_level ON lead_master (confidence_level);

-- 4. duplicate_events
CREATE TABLE IF NOT EXISTS duplicate_events (
    duplicate_event_id TEXT PRIMARY KEY,
    incoming_lead_id TEXT NOT NULL,
    matched_master_id TEXT REFERENCES lead_master(master_id) ON DELETE SET NULL,
    match_type TEXT NOT NULL,
    match_reason TEXT NOT NULL,
    quality_result_id TEXT REFERENCES quality_results(quality_result_id) ON DELETE SET NULL,
    research_job_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_duplicate_events_incoming_lead_id ON duplicate_events (incoming_lead_id);

-- 5. review_queue
CREATE TABLE IF NOT EXISTS review_queue (
    review_id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL,
    research_job_id TEXT,
    reason TEXT NOT NULL,
    lead_data JSONB NOT NULL DEFAULT '{}',
    confidence_score INTEGER,
    confidence_level TEXT,
    confidence_result_id TEXT REFERENCES confidence_results(confidence_result_id) ON DELETE SET NULL,
    quality_result_id TEXT REFERENCES quality_results(quality_result_id) ON DELETE SET NULL,
    issues JSONB NOT NULL DEFAULT '[]',
    conflicts JSONB NOT NULL DEFAULT '[]',
    evidence_refs JSONB NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'needs_more_research')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue (status);
CREATE INDEX IF NOT EXISTS idx_review_queue_confidence_level ON review_queue (confidence_level);
"""

def main():
    url = get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    print("Creating schema...")
    cur.execute(SCHEMA_SQL)

    # Verify tables
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' ORDER BY table_name
    """)
    tables = [t[0] for t in cur.fetchall()]
    print(f"Tables created ({len(tables)}): {tables}")

    # Verify indexes
    cur.execute("""
        SELECT indexname, tablename FROM pg_indexes
        WHERE schemaname = 'public' ORDER BY tablename, indexname
    """)
    idxs = cur.fetchall()
    print(f"Indexes created ({len(idxs)}):")
    for idx in idxs:
        print(f"  {idx[0]} on {idx[1]}")

    # Verify foreign keys
    cur.execute("""
        SELECT
            tc.table_name, kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
    """)
    fks = cur.fetchall()
    print(f"Foreign keys ({len(fks)}):")
    for fk in fks:
        print(f"  {fk[0]}.{fk[1]} -> {fk[2]}.{fk[3]}")

    cur.close()
    conn.close()
    print("\nSchema creation complete.")

if __name__ == "__main__":
    main()
