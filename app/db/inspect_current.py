"""Inspect current Supabase schema."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import psycopg2
from app.config import DATABASE_URL

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
print("Current tables:")
for r in cur.fetchall():
    print(f"  {r[0]}")

cur.execute("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'lead_master' ORDER BY ordinal_position")
print("\nlead_master columns:")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]} nullable={r[2]} default={r[3]}")

cur.execute("SELECT indexname, tablename FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename")
print("\nIndexes:")
for r in cur.fetchall():
    print(f"  {r[0]} on {r[1]}")

cur.execute("SELECT COUNT(*) FROM lead_master")
print(f"\nlead_master rows: {cur.fetchone()[0]}")

cur.close()
conn.close()
