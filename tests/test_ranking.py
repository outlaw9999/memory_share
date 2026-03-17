import pytest
import time
from pathlib import Path
from kit.core.kit_cognitive_core import SAMBrain

@pytest.fixture
def brain(tmp_path):
    db_path = tmp_path / "ranking_test.db"
    return SAMBrain(db_path)

def test_ranking_decay_and_saturation(brain):
    # 1. Old but high access fact
    fact1_id = brain.learn("node", "High frequency old fact", importance=1.0)
    for _ in range(10):
        brain.touch_fact(fact1_id)
        
    # 2. Fresh but low frequency fact
    fact2_id = brain.learn("node", "Fresh new fact", importance=10.0)
    
    # Manually simulate decay for fact1
    with brain._get_connection() as conn:
        conn.execute("UPDATE observations SET created_at = julianday('now', '-30 days') WHERE id = ?", (fact1_id,))
    
    results = brain.recall(["node"])
    
    # Fresh fact with high importance should be top, even if old fact has high access (saturation curve)
    assert results[0].content == "Fresh new fact"
    
def test_namespace_boost(brain):
    # 1. Fact in shared namespace
    brain.learn("ui", "Shared UI fact", namespace="shared")
    
    # 2. Fact in agent specific namespace
    brain.learn("ui", "My private UI fact", namespace="agent_alice", agent_id="agent_alice")
    
    # Recall with agent_id
    results = brain.recall(["ui"], agent_id="agent_alice")
    
    # Agent's own namespace should be boosted
    assert results[0].content == "My private UI fact"
