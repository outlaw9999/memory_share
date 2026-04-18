import sqlite3
import pytest
from pathlib import Path
from kit.core.memory_topology import MemoryTopologyFactory

def test_sqlite_physical_lock():
    """
    STABILIZATION AUDIT: Physical Lock (v1.2.4-STABILIZE-HARD)
    Proves that the Frozen Tier is physically read-only via SQLite URI mode=ro.
    """
    repo_root = Path.cwd().resolve()
    topology = MemoryTopologyFactory.for_project(repo_root)
    
    # Ensure the file exists (create it first if necessary via a normal connection)
    path = topology.resolve("global", "frozen")
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create file if missing
    temp_conn = sqlite3.connect(str(path))
    temp_conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)")
    temp_conn.close()
    
    # Now connect via authority (which uses mode=ro)
    conn = topology.connect("global", "frozen")
    
    with pytest.raises(sqlite3.OperationalError) as excinfo:
        conn.execute("INSERT INTO test (id) VALUES (1)")
    
    assert "readonly database" in str(excinfo.value).lower()
    print("SUCCESS: SQLite physical lock verified (attempted write blocked by mode=ro).")

if __name__ == "__main__":
    # Run manual check
    try:
        test_sqlite_physical_lock()
    except Exception as e:
        print(f"FAILED: {e}")
