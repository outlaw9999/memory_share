import sqlite3
import os
from pathlib import Path

db_path = Path.home() / ".kit" / "global.db"
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

print("--- OBSERVATIONS ---")
rows = conn.execute("SELECT o.*, n.uid FROM observations o JOIN nodes n ON o.node_id = n.id").fetchall()
for r in rows:
    print(f"ID:{r['id']} | UID:{r['uid']} | Branch:{r['branch']} | Content:{r['content'][:40]}...")

print("\n--- FTS ENTRIES ---")
fts_rows = conn.execute("SELECT rowid, * FROM observations_fts").fetchall()
for r in fts_rows:
    print(f"ROWID:{r['rowid']} | Content:{r['content'][:40]}...")

conn.close()
