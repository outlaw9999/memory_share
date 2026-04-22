import pytest
import sqlite3
import json
from pathlib import Path
from dataclasses import replace
from kit.core.kit_cognitive_core import Memory, SAMBrain
from kit.core.memory_router import MemoryRouter, MemoryWriteRequest, WriteSource, MemoryTier
from kit.core.kit_sealing import verify_kernel_seal, SEALED_VERSION

@pytest.fixture
def mock_db(tmp_path):
    db_path = tmp_path / "test_kernel.db"
    from kit.core.kit_sealing import seal_kernel
    seal_kernel(db_path)
    return db_path

# --- Level 1: Contract & DTO Tests ---

def test_memory_dto_immutability():
    """Verify that Memory objects are strictly frozen (Option A invariant)."""
    m = Memory(
        id=1, node_uid="test", content="content", score=1.0, 
        brain_source="local", metadata={"initial": True}
    )
    
    with pytest.raises(Exception): # dataclasses.FrozenInstanceError
        m.score = 2.0
    
    with pytest.raises(TypeError): # slots=True
        m.new_field = "drift"

def test_memory_to_dict_mapping():
    """Verify dumb mapping purity."""
    m = Memory(
        id=42, node_uid="uid_42", content="hello", score=0.9, 
        brain_source="global", tag="pattern", layer="semantic"
    )
    d = m.to_dict()
    assert d["uid"] == "uid_42"
    assert d["content"] == "hello"
    assert d["tag"] == "pattern"
    assert d["layer"] == "semantic"

# --- Level 2: Router & Write Authority Tests ---

def test_router_single_write_authority(mock_db):
    """Verify that all writes result in the expected schema projection."""
    from kit.core.memory_topology import MemoryTopology
    topology = MemoryTopology(project_root=mock_db.parent)
    
    # Manually configure router to use mock_db for local
    # Manually configure router to use mock_db for local
    # v1.2.5-STABLE: Use a SHARED connection context. 
    # Router will NOT close it because _owns_connection will be False.
    conn = sqlite3.connect(mock_db)
    conn.row_factory = sqlite3.Row
    
    def shared_conn_provider(path, readonly=False):
        return conn

    router = MemoryRouter(topology, local_db_path_override=mock_db, connection_provider=shared_conn_provider)
    
    request = MemoryWriteRequest(
        source=WriteSource.KIT_LEARN,
        key="test_node",
        content="Structural truth",
        confidence=0.8,
        metadata={"provenance": "test"},
        tag="decision",
        structural_hash="sha256:fakehash"
    )
    
    decision = router.route_write(request)
    assert decision.decision == "accepted"
    
    # Verify DB state directly (Same Connection - Instant Visibility)
    # No proxy needed anymore because router doesn't close external connections.
    row = conn.execute("SELECT * FROM observations WHERE id = ?", (decision.observation_id,)).fetchone()
    
    assert row is not None, f"Observation {decision.observation_id} not found in DB"
    assert row["content"] == "Structural truth"
    assert row["structural_hash"] == "sha256:fakehash"
    assert json.loads(row["metadata"])["provenance"] == "test"
    
    conn.close()

# --- Level 3: Sealing & Policy Enforcement ---

def test_kernel_seal_verification(mock_db):
    """Verify that the Sealing layer correctly identifies a v1.2.4-sealed DB."""
    info = verify_kernel_seal(mock_db)
    assert info["status"] == "sealed"
    assert info["version"] == SEALED_VERSION

def test_kernel_seal_violation(tmp_path):
    """Verify that an unsealed (legacy) DB is rejected."""
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY)")
    conn.close()
    
    info = verify_kernel_seal(db_path)
    assert info["status"] == "unsealed"

def test_kernel_version_lock(mock_db):
    """Verify the Kernel Constitution is persisted correctly."""
    conn = sqlite3.connect(mock_db)
    version = conn.execute("SELECT value FROM kernel_metadata WHERE key = 'version'").fetchone()[0]
    assert version == SEALED_VERSION
    conn.close()
