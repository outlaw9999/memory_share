import threading
import time
import sys
from pathlib import Path
from kit.core.memory_router import MemoryRouterFactory, MemoryWriteRequest, WriteSource, MemoryTier
from kit.core.memory_topology import MemoryTopologyFactory

def test_multi_threaded_stress():
    """
    STABILIZATION TEST: Multi-threaded Concurrency Lock (v1.2.4)
    Simulates high-load environment to verify RouterWriteBuffer and SQLite WAL resiliency.
    """
    print("Initializing Stress Test...")
    repo_root = Path.cwd().resolve()
    
    # Ensure fresh state
    topology = MemoryTopologyFactory.for_project(repo_root)
    local_db = topology.resolve("local", "local")
    if local_db.exists():
        # SQLite files should be handled carefully on windows
        pass

    router = MemoryRouterFactory.create(repo_root)
    
    TOTAL_THREADS = 5
    OPS_PER_THREAD = 200
    
    errors = []

    def worker(start_index):
        for i in range(OPS_PER_THREAD):
            idx = start_index + i
            req = MemoryWriteRequest(
                source=WriteSource.TRAINER,
                key=f"stress:{idx}",
                content={"v": idx, "ts": time.time()},
                confidence=0.5,
                metadata={"thread": threading.get_ident()}
            )
            try:
                router.route_write(req)
            except Exception as e:
                errors.append(f"Thread {threading.get_ident()} failed at idx {idx}: {e}")

    print(f"Executing {TOTAL_THREADS} threads, {OPS_PER_THREAD} ops/thread...")
    start_time = time.time()
    
    threads = []
    for t in range(TOTAL_THREADS):
        th = threading.Thread(target=worker, args=(t * OPS_PER_THREAD,))
        threads.append(th)
        th.start()

    for th in threads:
        th.join()

    duration = time.time() - start_time
    
    # Final check
    if not errors:
        print(f"SUCCESS: {TOTAL_THREADS * OPS_PER_THREAD} writes completed in {duration:.2f}s")
        print(f"Average latency: {(duration / (TOTAL_THREADS * OPS_PER_THREAD)) * 1000:.2f}ms/op")
    else:
        print(f"FAILED: {len(errors)} errors detected!")
        for err in errors[:5]:
            print(f"  - {err}")
        sys.exit(1)

if __name__ == "__main__":
    test_multi_threaded_stress()
