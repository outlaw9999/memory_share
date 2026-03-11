import sqlite3
import os

db_path = "e:/DEV/opensource_contrib/memory_share/.antigravity/atlas/atlas.db"
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("Schema for 'symbols' table:")
cur.execute("PRAGMA table_info(symbols)")
for row in cur.fetchall():
    print(row)

print("\nSchema for 'edges' table:")
cur.execute("PRAGMA table_info(edges)")
for row in cur.fetchall():
    print(row)

conn.close()
