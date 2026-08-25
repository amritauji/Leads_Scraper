"""SQLite database schema and initialization."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS quality_results (
    quality_result_id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL,
    research_job_id TEXT,
    original_lead TEXT NOT NULL,
    cleaned_lead TEXT NOT NULL,
    validation_results TEXT NOT NULL,
    duplicate_result TEXT NOT NULL,
    issues TEXT NOT NULL,
    conflicts TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS confidence_results (
    confidence_result_id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL,
    research_job_id TEXT,
    quality_result_id TEXT,
    score INTEGER NOT NULL,
    level TEXT NOT NULL,
    positive_factors TEXT NOT NULL,
    negative_factors TEXT NOT NULL,
    conflicts TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS duplicate_events (
    duplicate_event_id TEXT PRIMARY KEY,
    incoming_lead_id TEXT NOT NULL,
    matched_master_id TEXT,
    match_type TEXT NOT NULL,
    match_reason TEXT NOT NULL,
    quality_result_id TEXT,
    research_job_id TEXT,
    created_at TEXT NOT NULL
);

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
    confidence_result_id TEXT,
    quality_result_id TEXT,
    data_quality_issues TEXT,
    evidence_refs TEXT,
    raw_evidence_refs TEXT,
    review_id TEXT,
    source_lead_json TEXT,
    status TEXT DEFAULT 'accepted',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_queue (
    review_id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    lead_data TEXT NOT NULL,
    confidence_score INTEGER,
    confidence_level TEXT,
    confidence_result_id TEXT,
    quality_result_id TEXT,
    issues TEXT NOT NULL,
    conflicts TEXT NOT NULL,
    evidence_refs TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL
);
"""


def init_db(conn):
    """Create all tables if they don't exist."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()
