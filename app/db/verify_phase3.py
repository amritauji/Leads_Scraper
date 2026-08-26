"""Verify Phase 3 data in Supabase."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import psycopg2
from app.config import DATABASE_URL

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("=" * 70)
print("  PHASE 3 DATA VERIFICATION")
print("=" * 70)

# Table row counts
print("\n  Row counts:")
for table in ["users", "lead_master", "lead_assignments", "lead_pipeline_history", "lead_activities"]:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"    {table}: {count}")

# Users
print("\n  Users:")
cur.execute("SELECT user_id, name, email, role, is_active FROM users ORDER BY name")
for r in cur.fetchall():
    print(f"    {r[0]}: {r[1]} ({r[2]}) role={r[3]} active={r[4]}")

# Lead Master with Phase 3 fields
print("\n  Lead Master (Phase 3 fields):")
cur.execute("SELECT master_id, company_name, pipeline_stage, priority, assigned_to, next_action_type FROM lead_master ORDER BY created_at")
for r in cur.fetchall():
    print(f"    {r[0]}: {r[1]} stage={r[2]} priority={r[3]} assigned={r[4]} next_action={r[5]}")

# Assignment history
print("\n  Assignment history:")
cur.execute("SELECT master_id, assigned_to, assigned_by, action, reason FROM lead_assignments ORDER BY created_at")
for r in cur.fetchall():
    print(f"    {r[0]}: {r[1]} by {r[2]} action={r[3]} reason={r[4]}")

# Pipeline history
print("\n  Pipeline history:")
cur.execute("SELECT master_id, from_stage, to_stage, changed_by, reason FROM lead_pipeline_history ORDER BY created_at")
for r in cur.fetchall():
    print(f"    {r[0]}: {r[1]} -> {r[2]} by {r[3]} reason={r[4]}")

# Activities (sample)
print("\n  Activities (last 10):")
cur.execute("SELECT master_id, activity_type, performed_by, title FROM lead_activities ORDER BY created_at DESC LIMIT 10")
for r in cur.fetchall():
    print(f"    {r[0]}: {r[1]} by {r[2]} - {r[3]}")

# FK verification
print("\n  FK verification:")
cur.execute("""
    SELECT lm.master_id, lm.assigned_to, lm.pipeline_changed_by,
           u1.name as assignee_name, u2.name as changer_name
    FROM lead_master lm
    LEFT JOIN users u1 ON lm.assigned_to = u1.user_id
    LEFT JOIN users u2 ON lm.pipeline_changed_by = u2.user_id
    WHERE lm.assigned_to IS NOT NULL OR lm.pipeline_changed_by IS NOT NULL
""")
for r in cur.fetchall():
    print(f"    {r[0]}: assignee={r[3]} changer={r[4]}")

cur.close()
conn.close()
print("\n" + "=" * 70)
print("  VERIFICATION COMPLETE")
print("=" * 70)
