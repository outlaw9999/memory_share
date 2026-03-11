import sqlite3
import os

db_path = ".antigravity/atlas/atlas_v1.db"
if not os.path.exists(db_path):
    # Fallback to check if I am crazy
    db_path = ".antigravity/atlas/atlas.db"
    
if not os.path.exists(db_path):
    print(f"Error: Database not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

def get_count(table):
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]
    except:
        return "Table not found"

print(f"Symbols: {get_count('symbols')}")
print(f"Aliases: {get_count('symbol_aliases')}")
print(f"Edges: {get_count('edges')}")

# Check for Alias resolution rate as suggested by the user
try:
    cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE target_alias IN (SELECT normalized_alias FROM symbol_aliases)) * 1.0 / COUNT(*)
    FROM edges;
    """)
    rate = cur.fetchone()[0]
    print(f"Alias Resolution Rate: {rate:.2f}")
except Exception as e:
    print(f"Error calculating resolution rate: {e}")

conn.close()
