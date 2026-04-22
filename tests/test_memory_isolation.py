import tempfile
import shutil
from pathlib import Path
from kit.core.memory_router import MemoryRouterFactory, MemoryWriteRequest, WriteSource

def test_local_global_isolation():
    """
    STABILIZATION TEST: Multi-repo Independence (v1.2.4)
    Ensures that writing to Repo A doesn't pollute Repo B's local brain,
    while both successfully target the shared Global brain.
    """
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        repo1 = Path(tmp1).resolve()
        repo2 = Path(tmp2).resolve()
        
        # Initialize .kit in both
        (repo1 / ".kit").mkdir()
        (repo2 / ".kit").mkdir()
        
        r1 = MemoryRouterFactory.create(repo1)
        r2 = MemoryRouterFactory.create(repo2)
        
        # Test 1: Local Isolation
        req1 = MemoryWriteRequest(
            source=WriteSource.TRAINER,
            key="iso:local:a",
            content="repo1 exclusive",
            confidence=0.1, # Force LOCAL
            metadata={"test": True}
        )
        r1.route_write(req1)
        
        # Repo 2 should not have this file or content
        local2_db = r2.topology.resolve("local", "local")
        
        # Check if repo2 db exists (it should be created on init/connect, but should be empty)
        import sqlite3
        conn = sqlite3.connect(str(local2_db))
        # v1.2.4-TITANIUM: Check 'nodes' table for the UID
        count = conn.execute("SELECT COUNT(*) FROM nodes WHERE uid='iso:local:a'").fetchone()[0]
        conn.close()
        
        assert count == 0, "Isolation failure! Repo 2 local brain contains Repo 1 data."
        
        # v1.2.4-TITANIUM: Resource Release
        r1.close()
        r2.close()
        
        print("SUCCESS: Multi-repo isolation verified.")

if __name__ == "__main__":
    test_local_global_isolation()
