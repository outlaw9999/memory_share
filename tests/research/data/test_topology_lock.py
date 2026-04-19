import pytest
from pathlib import Path
from kit.core.memory_topology import MemoryTopologyFactory

def test_topology_paths_locked():
    """
    STABILIZATION LOCK: v1.2.4-COLLAPSE-SAFE
    Ensures memory tier naming is deterministic and geographically locked.
    """
    # Mock repo root for stable testing
    repo_root = Path("E:/DEV/opensource_contrib/memory_share_kit").resolve()
    
    topology = MemoryTopologyFactory.for_project(repo_root)
    
    # 1. LOCAL TIER
    local_path = topology.resolve("local", "local")
    assert local_path.name == "local_brain.db", "Local brain naming drift detected!"
    assert local_path.parent.name == ".kit", "Local brain location drift detected!"
    assert str(repo_root) in str(local_path), "Local brain not anchored to repo root!"
    
    # 2. GLOBAL TIER
    global_path = topology.resolve("global", "global")
    assert global_path.name == "global_brain.db", "Global brain naming drift detected!"
    assert ".kit" in str(global_path), "Global brain not in .kit home!"
    
    # 3. FROZEN TIER
    frozen_path = topology.resolve("global", "frozen")
    assert frozen_path.name == "global_read_only.db", "Frozen brain naming drift detected!"
    
    snapshot_path = topology.resolve("local", "snapshot")
    assert snapshot_path.name == "memory_snapshot.db", "Snapshot tier naming drift detected!"
    assert snapshot_path.parent.name == ".kit", "Snapshot location drift detected!"
    
    # 4. AUDIT TIER
    audit_path = topology.resolve("global", "audit")
    assert audit_path.name == "router_decisions.jsonl", "Audit log naming drift detected!"

    print("\n[TOPOLOGY LOCK] All paths deterministic and verified.")
