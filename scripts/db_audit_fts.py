import sqlite3
import os
import sys
from pathlib import Path

# Force UTF-8 for printing
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

db_path = Path.home() / ".kit" / "global.db"
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

print("--- FTS SEARCH TEST ---")
query = "typed interfaces"
fts_rows = conn.execute("SELECT rowid FROM observations_fts WHERE observations_fts MATCH ?", (query,)).fetchall()
print(f"FTS found {len(fts_rows)} matches for '{query}'")

print("\n--- OBSERVATIONS FOR MATCHED ROWIDS ---")
for r in fts_rows:
    obs = conn.execute("SELECT * FROM observations WHERE id = ?", (r["rowid"],)).fetchone()
    if obs:
        print(f"ID:{obs['id']} | Branch:{obs['branch']} | Content:{obs['content']}")

conn.close()
