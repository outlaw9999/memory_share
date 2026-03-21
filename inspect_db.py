import sqlite3
import os

db_path = ".kit/brain.db"
try:
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found")
        exit(1)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables in {db_path}:")
    for table in tables:
        print(f"\nTable: {table[0]}")
        cursor.execute(f"PRAGMA table_info({table[0]})")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
