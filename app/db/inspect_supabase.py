"""Inspect current Supabase database state."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.config import get
import psycopg2

url = get("DATABASE_URL")
if not url:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

print("Connecting to Supabase PostgreSQL...")
conn = psycopg2.connect(url)
cur = conn.cursor()

# List all tables
cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' ORDER BY table_name
""")
tables = [t[0] for t in cur.fetchall()]
print(f"\nExisting tables ({len(tables)}): {tables if tables else 'NONE'}")

# Check columns for each table
for table in tables:
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    cols = cur.fetchall()
    print(f"\n  {table}:")
    for col in cols:
        print(f"    {col[0]}: {col[1]} (nullable={col[2]})")

# Check foreign keys
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
print(f"\nForeign keys ({len(fks)}):")
for fk in fks:
    print(f"  {fk[0]}.{fk[1]} -> {fk[2]}.{fk[3]}")

# Check indexes
cur.execute("""
    SELECT indexname, tablename
    FROM pg_indexes
    WHERE schemaname = 'public'
    ORDER BY tablename, indexname
""")
idxs = cur.fetchall()
print(f"\nIndexes ({len(idxs)}):")
for idx in idxs:
    print(f"  {idx[0]} on {idx[1]}")

# Row counts
print("\nRow counts:")
for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"  {table}: {count} rows")

cur.close()
conn.close()
print("\nDone.")
