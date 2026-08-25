"""Verify test data in Supabase after Phase 2 tests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.config import get
import psycopg2
import psycopg2.extras
import json

url = get("DATABASE_URL")
conn = psycopg2.connect(url)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

print("=" * 70)
print("  SUPABASE DATA VERIFICATION")
print("=" * 70)

# Row counts
print("\n  Row counts:")
for table in ["quality_results", "confidence_results", "lead_master", "duplicate_events", "review_queue"]:
    cur.execute(f"SELECT COUNT(*) as cnt FROM {table}")
    count = cur.fetchone()["cnt"]
    print(f"    {table}: {count}")

# Verify Lead Master lineage
print("\n  Lead Master records:")
cur.execute("SELECT master_id, lead_id, company_name, confidence_score, confidence_level, confidence_result_id, quality_result_id, review_id, research_job_id, status FROM lead_master ORDER BY created_at")
for row in cur.fetchall():
    print(f"    {row['master_id']}: {row['company_name']} (score={row['confidence_score']}, level={row['confidence_level']}, status={row['status']})")
    print(f"      confidence_result_id: {row['confidence_result_id']}")
    print(f"      quality_result_id:    {row['quality_result_id']}")
    print(f"      review_id:            {row['review_id']}")
    print(f"      research_job_id:      {row['research_job_id']}")

# Verify FK relationships
print("\n  Foreign key verification:")
cur.execute("""
    SELECT lm.master_id, lm.confidence_result_id, lm.quality_result_id,
           cr.confidence_result_id as cr_exists,
           qr.quality_result_id as qr_exists
    FROM lead_master lm
    LEFT JOIN confidence_results cr ON lm.confidence_result_id = cr.confidence_result_id
    LEFT JOIN quality_results qr ON lm.quality_result_id = qr.quality_result_id
""")
for row in cur.fetchall():
    cr_ok = "OK" if row["cr_exists"] else "BROKEN"
    qr_ok = "OK" if row["qr_exists"] else "BROKEN"
    print(f"    {row['master_id']}: CR={cr_ok}, QR={qr_ok}")

# Verify JSONB fields
print("\n  JSONB field check (lead_master.source_lead_json):")
cur.execute("SELECT master_id, source_lead_json->>'LeadId' as lead_id FROM lead_master")
for row in cur.fetchall():
    print(f"    {row['master_id']}: source_lead_json.LeadId = {row['lead_id']}")

# Verify duplicate events
print("\n  Duplicate events:")
cur.execute("SELECT * FROM duplicate_events")
for row in cur.fetchall():
    print(f"    {row['duplicate_event_id']}: {row['incoming_lead_id']} -> {row['matched_master_id']} ({row['match_reason']})")

# Verify review queue
print("\n  Review queue (all statuses):")
cur.execute("SELECT review_id, lead_id, status, confidence_score, confidence_level, reason FROM review_queue")
for row in cur.fetchall():
    print(f"    {row['review_id']}: {row['lead_id']} status={row['status']} score={row['confidence_score']} reason={row['reason']}")

# Verify indexes
print("\n  Indexes:")
cur.execute("SELECT indexname, tablename FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'idx_%' ORDER BY tablename")
for row in cur.fetchall():
    print(f"    {row['indexname']} on {row['tablename']}")

cur.close()
conn.close()
print("\n" + "=" * 70)
print("  VERIFICATION COMPLETE")
print("=" * 70)
