import sqlite3
import time
from pathlib import Path

import pytest

from kit.core.kit_cognitive_core import FactTag, SAMBrain
from kit.core.kit_reflect import run_reflect


@pytest.fixture
def brain(tmp_path):
    db_path = tmp_path / "test_amsb.db"
    return SAMBrain(db_path)


def test_authority_hierarchy(brain):
    """
    Test 1: Authority Hierarchy (invariant > decision > preference > note)
    """
    # Learn facts with different tags sharing the same symbol but unique UIDs to avoid shadowing if desired,
    # but here we test Symbol-based authority ranking.
    # We keep importance low (< 0.6 confidence) to stay in LOCAL tier.
    brain.learn("db_q1", "Use PostgreSQL", symbol="db_choice", tag="decision", importance=0.5)
    brain.learn("db_q2", "MUST use SQLite", symbol="db_choice", tag="invariant", importance=0.4)
    brain.learn("db_q3", "Maybe use Redis", symbol="db_choice", tag="note", importance=0.5)

    # Recall
    results = brain.recall(["db_choice"])

    # Invariant should be top despite lower importance because of primary sort by tag
    assert len(results) >= 2, f"Expected at least 2 results, got {len(results)}"
    assert results[0].tag == "invariant", f"Expected 'invariant' but got '{results[0].tag}'"
    assert "SQLite" in results[0].content
    assert results[1].tag == "decision"


def test_preflight_snapshot_avoids_live_brain(tmp_path):
    """
    Test snapshot creation for read-only cognitive preflight.
    """
    db_path = tmp_path / ".kit" / "local_brain.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    brain = SAMBrain(db_path, root_path=tmp_path)
    brain.learn("env", "Prefer WAL mode for SQLite", tag="decision", importance=0.7)

    # Trigger metadata query path that uses snapshot copy.
    obs = brain.recall([], limit=5)
    assert len(obs) == 1
    assert obs[0].tag == "decision"

    # v1.2.5: Ensure snapshot is created
    brain.snapshot()
    snapshot_path = brain.topology.resolve("local", "snapshot")
    assert snapshot_path.exists()
    assert snapshot_path.stat().st_size > 0


def test_global_brain_rejects_local_cognition_tags(brain):
    """
    Test contract: local cognition tags may not be promoted to GLOBAL.
    """
    with pytest.raises(ValueError, match="Global memory cannot store local cognition tags"):
        brain.learn("db_choice", "Avoid global decision tagging", tag="decision", to_global=True)


def test_snapshot_syncer_refreshes_after_local_write(tmp_path):
    """
    Test that background snapshot sync refreshes the read-only copy after local writes.
    """
    db_path = tmp_path / ".kit" / "local_brain.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    brain = SAMBrain(db_path, root_path=tmp_path)
    # v1.2.5: Force start syncer for background sync verification
    brain._start_snapshot_syncer()

    brain.learn("sync", "Local change triggers snapshot refresh", tag="decision", importance=0.8)

    snapshot_path = brain.topology.resolve("local", "snapshot")
    for _ in range(10):
        if snapshot_path.exists() and snapshot_path.stat().st_size > 0:
            break
        time.sleep(0.5)

    assert snapshot_path.exists(), "Snapshot file should be created by syncer"
    assert snapshot_path.stat().st_size > 0


def test_immutable_ledger_supersede(brain):
    """
    Test 2: Immutable Ledger (Lineage & is_active)
    """
    # Use unique content to avoid idempotency hits from other tests
    content1 = f"Use JWT {time.time()}"
    content2 = f"Use OAuth2 {time.time()}"

    id1 = brain.learn("auth", content1, tag="decision")

    # Supersede id1 with id2
    id2 = brain.learn("auth", content2, tag="decision", supersede_id=id1)

    with brain.get_connection() as conn:
        # Check id1 (Old)
        row1 = conn.execute("SELECT is_active, superseded_at FROM observations WHERE id = ?", (id1,)).fetchone()
        assert row1["is_active"] == 0
        assert row1["superseded_at"] is not None

        # Check id2 (New)
        row2 = conn.execute(
            "SELECT is_active, superseded_at, supersedes_id FROM observations WHERE id = ?", (id2,)
        ).fetchone()
        assert row2["is_active"] == 1
        assert row2["superseded_at"] is None
        assert row2["supersedes_id"] == id1


def test_compute_at_write_materialized_score(brain):
    """
    Test 3: Compute-at-Write (Score precomputation)
    """
    fact_id = brain.learn("cache", "Use Redis", tag="decision", importance=0.8)

    with brain.get_connection() as conn:
        row = conn.execute("SELECT materialized_score FROM observations WHERE id = ?", (fact_id,)).fetchone()
        assert row["materialized_score"] > 0
        # Formula v1.2.5: 0.8 * (0+2)/(0+6.0) = 0.8 * 0.3333 = 0.2666
        assert pytest.approx(row["materialized_score"], 0.01) == 0.2666


def test_preflight_blocks_invariant_violation(brain):
    """
    Test 4: Preflight/Reflection blocking
    """
    # 1. Learn an Invariant (Lower importance: 0.1)
    brain.learn("security", "NEVER log passwords", tag="invariant", importance=0.1)

    # 2. Learn a Decision (Higher importance: 1.0)
    # 1.0 * 0.333 + 0.2 (bonus) = 0.533  vs  0.1 * 0.333 + 0.3 (bonus) = 0.333
    brain.learn("security", "It is okay to log in debug", tag="decision", importance=1.0)

    # Run reflect
    diff = "import security\n+ logging.log(password)"
    report = run_reflect(brain, diff)

    # The Decision wins the score but because an Invariant exists for the same signal,
    # resolve_cognitive_conflict should return is_violation=True.
    assert report.status == "BLOCK"
    assert "security" in report.resolutions
    assert report.resolutions["security"].is_violation is True


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

    # None of these should be in gaps (gaps are reported as signals with GAP: prefix)
    gaps = [s for s in report.signals if s.uid.startswith("GAP:")]
    assert len(gaps) == 0
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
    report = run_reflect(brain, diff)

    # Two invariants conflict -> Should still be BLOCK
    assert report.status == "BLOCK"
    # But resolve_cognitive_conflict just picks the best invariant currently.
    # In v1.1, if there are multiple invariants, it just picks the one with highest score.
    # Wait, the spec says "Invariants are the law".
    # If they conflict, it's a mess.
    assert "auth" in report.resolutions
