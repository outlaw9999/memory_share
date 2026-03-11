import sqlite3
import os

db_path = "e:/DEV/opensource_contrib/memory_share/.antigravity/atlas/atlas.db"
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("Schema for 'calls' table:")
cur.execute("PRAGMA table_info(calls)")
for row in cur.fetchall():
    print(row)

print("\nSample data from 'calls':")
cur.execute("SELECT * FROM calls LIMIT 5")
for row in cur.fetchall():
    print(row)

conn.close()
