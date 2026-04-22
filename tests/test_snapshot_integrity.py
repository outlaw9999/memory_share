import pytest
import sqlite3
import hashlib
import json
import time
from pathlib import Path
from kit.core.kit_cognitive_core import SAMBrain, sha256_file

def test_snapshot_integrity_titanium_plus(tmp_path):
    """
    TITANIUM++ INTEGRITY TEST: Verifies the manifest-based hash-chain.
    """
    db_path = tmp_path / "live_plus.db"
    brain = SAMBrain(db_path)
    
    # 1. First snapshot
    brain.learn("node_1", "Initial Content")
    snap1_path = brain.snapshot(reason="Genesis")
    
    with brain.get_connection(readonly=True) as conn:
        row = conn.execute("SELECT id, parent_hash, snapshot_hash, metadata FROM snapshots").fetchone()
        snap_id = row[0]
        p_hash = row[1]
        s_hash = row[2]
        meta = json.loads(row[3])
        
        assert p_hash == "GENESIS"
        file_hash = sha256_file(snap1_path)
        
        # Verify Manifest
        manifest = f"{p_hash}|{file_hash}|{meta['ts_bucket']}|{snap_id}|v1.2.4"
        expected = hashlib.sha256(manifest.encode()).hexdigest()
        assert s_hash == expected
        
    # 2. Second snapshot (Chaining)
    time.sleep(1.1) # Ensure different bucket
    brain.learn("node_2", "Second Content")
    snap2_path = brain.snapshot(reason="Link 2")
    
    with brain.get_connection(readonly=True) as conn:
        rows = conn.execute("SELECT id, parent_hash, snapshot_hash, metadata FROM snapshots ORDER BY timestamp ASC").fetchall()
        assert len(rows) == 2
        
        # Chain Link: Current parent == Previous snapshot_hash
        assert rows[1]["parent_hash"] == rows[0]["snapshot_hash"]
        
    print("\n[*] Titanium++ Integrity Chain Verified.")

def test_atomic_snapshot_safety(tmp_path):
    """
    Verifies that snapshots are created atomically.
    """
    db_path = tmp_path / "atomic.db"
    brain = SAMBrain(db_path)
    
    brain.learn("node_1", "Data")
    snap_path = brain.snapshot()
    
    assert snap_path.exists()
    assert not snap_path.with_suffix(".tmp").exists()
    print("[*] Atomic write verified (no lingering .tmp).")

if __name__ == "__main__":
    pytest.main([__file__])
