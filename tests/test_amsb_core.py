import pytest
import sqlite3
import time
from pathlib import Path
from kit.core.kit_cognitive_core import SAMBrain, FactTag
from kit.core.kit_reflect import run_reflect

@pytest.fixture
def brain(tmp_path):
    db_path = tmp_path / "test_amsb.db"
    return SAMBrain(db_path)

def test_authority_hierarchy(brain):
    """
    Test 1: Authority Hierarchy (invariant > decision > preference > note)
    """
    # Learn facts with different tags
    brain.learn("db_choice", "Use PostgreSQL", tag="decision", importance=1.0)
    brain.learn("db_choice", "MUST use SQLite", tag="invariant", importance=0.5) # Lower importance but higher tag
    brain.learn("db_choice", "Maybe use Redis", tag="note", importance=1.0)
    
    # Recall
    results = brain.recall(["db_choice"])
    
    for i, r in enumerate(results):
        print(f"  {i+1}. [{r.tag}] Score: {r.score:.4f} - {r.content}")
    
    # Invariant should be top despite lower importance because of primary sort by tag
    assert results[0].tag == "invariant", f"Expected 'invariant' but got '{results[0].tag}'"
    assert "SQLite" in results[0].content
    assert results[1].tag == "decision"

def test_immutable_ledger_supersede(brain):
    """
    Test 2: Immutable Ledger (Lineage & is_active)
    """
    id1 = brain.learn("auth", "Use JWT", tag="decision")
    
    # Supersede id1 with id2
    id2 = brain.learn("auth", "Use OAuth2", tag="decision", supersede_id=id1)
    
    with brain._get_connection() as conn:
        # Check id1 (Old)
        row1 = conn.execute("SELECT is_active, superseded_at FROM observations WHERE id = ?", (id1,)).fetchone()
        assert row1["is_active"] == 0
        assert row1["superseded_at"] is not None
        
        # Check id2 (New)
        row2 = conn.execute("SELECT is_active, superseded_at, supersedes_id FROM observations WHERE id = ?", (id2,)).fetchone()
        assert row2["is_active"] == 1
        assert row2["superseded_at"] is None
        assert row2["supersedes_id"] == id1

def test_compute_at_write_materialized_score(brain):
    """
    Test 3: Compute-at-Write (Score precomputation)
    """
    fact_id = brain.learn("cache", "Use Redis", tag="decision", importance=0.8)
    
    with brain._get_connection() as conn:
        row = conn.execute("SELECT materialized_score FROM observations WHERE id = ?", (fact_id,)).fetchone()
        assert row["materialized_score"] > 0
        # Formula: 0.8 * log10(0+2) * (1/sqrt(0+1)) = 0.8 * 0.301 * 1 = 0.2408
        assert pytest.approx(row["materialized_score"], 0.01) == 0.2408

def test_preflight_blocks_invariant_violation(brain):
    """
    Test 4: Preflight/Reflection blocking
    """
    # 1. Learn an Invariant (Lower importance: 0.4)
    brain.learn("security", "NEVER log passwords", tag="invariant", importance=0.4)
    
    # 2. Learn a Decision (Higher importance: 1.0)
    # Even with tag bonus 0.3 vs 0.2, the Decision will win because 1.0*log10(2)+0.2 > 0.4*log10(2)+0.3
    # 0.301 + 0.2 = 0.501  vs  0.4*0.301 + 0.3 = 0.12 + 0.3 = 0.42
    brain.learn("security", "It is okay to log in debug", tag="decision", importance=1.0)
    
    # Run reflect
    diff = "import security\n+ logging.log(password)"
    report = run_reflect(brain, diff)
    
    # The Decision wins the score but because an Invariant exists for the same signal, 
    # resolve_cognitive_conflict should return is_violation=True.
    assert report.status == "BLOCK"
    assert "security" in report.violations

def test_full_cognitive_loop(brain):
    """
    Test 5: Full Cognitive Loop (learn -> recall -> reflect)
    """
    # 1. Learn
    brain.learn("auth_service", "Auth tokens must have 30s skew tolerance", tag="invariant")
    
    # 2. Recall (Internal check)
    memories = brain.recall(["auth_service"])
    assert len(memories) > 0
    assert "30s" in memories[0].content
    
    # 3. Reflect
    diff = "import auth_service\n+ validate_token(now)"
    report = run_reflect(brain, diff)
    
    # Should find confirmation since there's no conflict
    assert report.status == "PASS"
    assert "auth_service" in report.confirmations

def test_hard_authority_invariant_wins(brain):
    """
    Test 6: Hard Authority (Invariant wins even if decision has higher score)
    """
    # Global invariant (lower score bonus +0.1)
    brain.learn("db", "Use SQLite", tag="invariant", importance=0.4)
    # Local decision (higher score bonus +0.2)
    brain.learn("db", "Use Postgres", tag="decision", scope="src", importance=1.0)
    
    # In recall, Invariant should still be prioritized by the engine due to tag sort
    results = brain.recall(["db"], here=True)
    assert results[0].tag == "invariant"
    
    # In reflect, resolve_cognitive_conflict should return violation if any invariant is overridden
    diff = "import db\n+ connect()"
    report = run_reflect(brain, diff, scope="src")
    assert report.status == "BLOCK"
    assert "violation" in report.suggestions[0].lower()

def test_stdlib_ignored_in_gaps(brain):
    """
    Test 7: Stdlib noise reduction
    """
    diff = "import os\nimport sys\nimport datetime\n+ print(now)"
    report = run_reflect(brain, diff)
    
    # None of these should be in gaps
    assert len(report.gaps) == 0
    assert report.status == "PASS"

def test_invariant_conflict_blocks(brain):
    """
    Test 8: Conflicting Invariants (Chaos mode)
    """
    brain.learn("auth", "Use JWT", tag="invariant")
    brain.learn("auth", "Use Session", tag="invariant")
    
    diff = "import auth\n+ authenticate()"
    report = run_reflect(brain, diff)
    
    # Two invariants conflict -> Should still be BLOCK
    assert report.status == "BLOCK"
    # But resolve_cognitive_conflict just picks the best invariant currently.
    # In v1.1, if there are multiple invariants, it just picks the one with highest score.
    # Wait, the spec says "Invariants are the law".
    # If they conflict, it's a mess.
    assert "auth" in report.resolutions
