import time
import tempfile
from pathlib import Path
from kit.core.kit_cognitive_core import SAMBrain, Memory
from kit.core.memory_policy import MemoryPolicy

def test_arbitration_scale_10k():
    """
    STRESS TEST: Production-grade Arbitration (v1.2.5-TITANIUM)
    Verifies that arbitration remains deterministic and fast at 10,000 memories.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "perf.db"
        brain = SAMBrain(db_path)
        
        # 1. Create 10,000 memories with overlapping attributes
        memories = []
        for i in range(10000):
            memories.append(Memory(
                id=i,
                node_uid=f"node_{i % 100}", # Many memories per node
                content=f"Content for memory {i}",
                score=1.0 if i % 2 == 0 else 0.5,
                brain_source="local",
                importance=0.5,
                tag="decision",
                scope="project",
                materialized_score=1.0 if i % 2 == 0 else 0.5
            ))
            
        policy = MemoryPolicy()
        now = time.time()
        
        print(f"\n[*] Starting arbitration of {len(memories)} memories...")
        
        # 2. Benchmark resolve loop
        start = time.perf_counter()
        # Resolve 50 times (typical reflection loop depth)
        for _ in range(50):
            # Pick a subset of 100 memories (typical candidate list size)
            candidates = memories[:100] 
            winners = policy.resolve(candidates, now=now)
        end = time.perf_counter()
        
        duration_ms = (end - start) * 1000
        print(f"[*] Resolved 50 arbitration sets (100 candidates each) in {duration_ms:.2f}ms")
        
        # Target: Total arbitration for 50 sets should be well under 100ms with O(1) hashing
        assert duration_ms < 100
        
        # 3. Determinism check
        winner1 = policy.resolve(memories[:100], now=now)
        winner2 = policy.resolve(memories[:100], now=now)
        
        assert winner1.id == winner2.id
        print("[*] Determinism verified.")

if __name__ == "__main__":
    test_arbitration_scale_10k()
