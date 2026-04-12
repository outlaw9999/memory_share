import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from kit import api


def benchmark():
    db_path = Path("bench.db")
    if db_path.exists():
        db_path.unlink()

    print("🚀 Initializing SAMBrain Bench...")
    api.init_kernel(db_path)

    # 1. Ingestion Test
    print("📥 Ingesting facts...")
    start_ingest = time.perf_counter()
    api.learn("infra", "core", "The infrastructure is connecting the nodes.", metadata={"layer": 4})
    api.learn("infra", "core", "Porter tokenizer stems words like connections and connected.", metadata={"layer": 4})
    api.learn("agent", "logic", "AI Agents prefer deterministic tools.", metadata={"tier": "primary"})

    for i in range(100):
        api.learn(f"entity_{i}", "bulk", f"This is random content fact number {i} for benchmarking search.")

    end_ingest = time.perf_counter()
    print(f"✅ Ingested 103 facts in {(end_ingest - start_ingest) * 1000:.2f}ms")

    # 2. FTS5 Search + Porter Tokenization Test
    print("\n🔍 Testing FTS5 Search (Porter Stemming)...")
    queries = ["connect", "agent", "bench"]
    for q in queries:
        start_q = time.perf_counter()
        results = api.search(q, limit=5)
        end_q = time.perf_counter()

        latency = (end_q - start_q) * 1000
        print(f"  - Query '{q}': {len(results)} results in {latency:.2f}ms")
        for r in results:
            print(f"    • [{r.entity_uid}] {r.content}")

    # 3. Metadata Test
    print("\n📦 Testing Metadata Escape Hatch...")
    _res = api.search("infrastructure", limit=1)
    # We need a way to get the metadata, for now let's just check the DB directly via a dirty query
    brain = api.get_brain()
    with brain._get_connection() as conn:
        row = conn.execute("SELECT metadata FROM facts WHERE content LIKE '%infrastructure%'").fetchone()
        print(f"  - Raw Metadata: {row['metadata']}")

    # Cleanup
    # db_path.unlink()


if __name__ == "__main__":
    benchmark()
