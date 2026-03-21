import sqlite3
import os
from pathlib import Path

db_path = Path.home() / ".kit" / "global.db"
if not db_path.exists():
    print(f"Error: {db_path} does not exist.")
    exit(1)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM observations WHERE content LIKE '%typed interfaces%'").fetchall()
print(f"Found {len(rows)} matching observations in Global DB.")
for r in rows:
    print(f"ID:{r['id']} | Active:{r['is_active']} | Branch:{r['branch']} | Content:{r['content']}")
conn.close()
