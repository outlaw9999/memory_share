import sqlite3
import sys
from pathlib import Path
from kit.core.memory_topology import MemoryTopologyFactory

def verify_wal():
    """
    STABILIZATION AUDIT: WAL Mode Enforcement (v1.2.4)
    Queries all 3 tiers to ensure journal_mode is 'wal'.
    """
    repo_root = Path.cwd().resolve()
    topology = MemoryTopologyFactory.for_project(repo_root)
    
    tiers = [
        ("local", "local"),
        ("global", "global"),
        ("global", "frozen")
    ]
    
    all_ok = True
    print("Verifying SQLite journal_mode across all tiers...")
    
    for scope, db_type in tiers:
        path = topology.resolve(scope, db_type)
        if not path.exists():
            print(f"  ? {scope}/{db_type}: File not found (skipping)")
            continue
            
        try:
            # Connect via authority to ensure PRAGMAs are applied if not already
            conn = topology.connect(scope, db_type)
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            conn.close()
            
            status = "OK" if mode.lower() == "wal" or (db_type == "frozen" and mode.lower() == "ro") else "FAIL"
            print(f"  [{status}] {scope}/{db_type}: {mode}")
            
            if status == "FAIL":
                all_ok = False
        except Exception as e:
            print(f"  [ERROR] {scope}/{db_type}: {e}")
            all_ok = False

    if not all_ok:
        sys.exit(1)

if __name__ == "__main__":
    verify_wal()
