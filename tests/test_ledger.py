import pytest
import sqlite3
from pathlib import Path
from kit.core.kit_cognitive_core import SAMBrain

@pytest.fixture
def brain(tmp_path):
    db_path = tmp_path / "test_brain.db"
    return SAMBrain(db_path)

def test_ledger_append_only(brain):
    # 1. Learn v1
    fact1_id = brain.learn("test_node", "Content V1")
    
    # Check initial state
    with brain._get_connection() as conn:
        row = conn.execute("SELECT content, superseded_at FROM observations WHERE id = ?", (fact1_id,)).fetchone()
        assert row["content"] == "Content V1"
        assert row["superseded_at"] is None

    # 2. Learn v2 superseding v1
    fact2_id = brain.learn("test_node", "Content V2", supersede_id=fact1_id)
    
    # Check ledger integrity
    with brain._get_connection() as conn:
        # v1 should be superseded
        v1_row = conn.execute("SELECT content, superseded_at FROM observations WHERE id = ?", (fact1_id,)).fetchone()
        assert v1_row["content"] == "Content V1"
        assert v1_row["superseded_at"] is not None
        
        # v2 should be active
        v2_row = conn.execute("SELECT content, superseded_at FROM observations WHERE id = ?", (fact2_id,)).fetchone()
        assert v2_row["content"] == "Content V2"
        assert v2_row["superseded_at"] is None

def test_node_identity_persistence(brain):
    # Multiple facts on same node should not duplicate node
    brain.learn("auth", "First fact")
    brain.learn("auth", "Second fact")
    
    with brain._get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM nodes WHERE uid = 'auth'").fetchone()[0]
        assert count == 1
