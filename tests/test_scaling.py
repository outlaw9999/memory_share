import time

import pytest

from kit.core.kit_cognitive_core import SAMBrain


@pytest.fixture
def brain(tmp_path):
    db_path = tmp_path / "scaling_test.db"
    return SAMBrain(db_path, root_path=tmp_path)


def test_scaling_10k_observations(brain):
    """
    Titanium Scaling Test (Priority 3).
    Verify that search and recall stay sub-100ms with 10,000 observations.
    """
    total_obs = 10000
    print(f"\n[SCALING] Ingesting {total_obs} observations...")

    start_ingest = time.perf_counter()
    # Batch ingest simulation (using a single transaction for speed if we were doing it in bulk,
    # but here we test the learn() overhead)
    # To speed up the test, we'll use a transaction
    with brain.get_connection() as conn:
        conn.execute("BEGIN")
        for i in range(total_obs):
            # We bypass the full learn() cycle for speed in seeding,
            # but we use the real schema
            content = f"Observation {i}: The quick brown fox jumps over the lazy dog. Index {i % 100}"
            uid = f"obs_{i}"

            # Simple manual insert to avoid 10k fsm frames in a test
            conn.execute(
                "INSERT INTO nodes (uid, node_type, status, visibility) VALUES (?, ?, ?, ?)",
                (uid, "observation", "active", "local"),
            )
            node_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO observations (node_id, content, layer, tag, importance, materialized_score, symbol) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (node_id, content, "episodic", "note", 0.5, 0.5, uid),
            )
            obs_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO observations_fts(rowid, content) VALUES (?, ?)", (obs_id, content))

        conn.commit()

    duration_ingest = time.perf_counter() - start_ingest
    print(f"[SCALING] Ingested 10k in {duration_ingest:.2f}s ({(total_obs / duration_ingest):.1f} obs/sec)")

    # 1. Search Latency Test
    print("[SCALING] Testing Search latency...")
    latencies = []
    for i in range(20):
        query = f"Index {i * 5}"
        start_search = time.perf_counter()
        results = brain.search(query, limit=10)
        latencies.append((time.perf_counter() - start_search) * 1000)
        assert len(results) > 0

    avg_search = sum(latencies) / len(latencies)
    print(f"[SCALING] Average Search Latency: {avg_search:.2f}ms")
    assert avg_search < 100, f"Search too slow: {avg_search:.2f}ms"

    # 2. Recall Latency Test
    print("[SCALING] Testing Recall latency...")
    latencies = []
    for i in range(20):
        entity = f"obs_{i * 500}"
        start_recall = time.perf_counter()
        results = brain.recall([entity])
        latencies.append((time.perf_counter() - start_recall) * 1000)
        assert len(results) > 0

    avg_recall = sum(latencies) / len(latencies)
    print(f"[SCALING] Average Recall Latency: {avg_recall:.2f}ms")
    assert avg_recall < 100, f"Recall too slow: {avg_recall:.2f}ms"
