import sqlite3
import os
import shutil

DB_PATH = "test_cleanup.db"

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

print(f"Testing SQLite initialization on {DB_PATH}...")

try:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print("Creating basic table...")
    cur.execute("CREATE TABLE symbols (id INTEGER PRIMARY KEY, fqn TEXT UNIQUE)")
    
    print("Inserting data...")
    cur.execute("INSERT INTO symbols (fqn) VALUES ('test.symbol')")
    
    print("Testing DELETE...")
    cur.execute("DELETE FROM symbols")
    
    print("Creating FTS5 table...")
    # This might be the failure point if FTS5 is not stable in this env
    SYMBOL_FTS_USING = """
    fts5(
        name,
        content='symbols',
        content_rowid='id',
        tokenize='unicode61',
        prefix='2 3'
    )
    """
    cur.execute(f"CREATE VIRTUAL TABLE symbol_fts USING {SYMBOL_FTS_USING}")
    
    conn.commit()
    print("Success! Basic SQLite and FTS5 work.")
    conn.close()
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
finally:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
