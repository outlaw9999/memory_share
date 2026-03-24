import multiprocessing
import sys
import time
from pathlib import Path

# Add parent to path so we can import runtime.lock_manager
sys.path.append(str(Path(__file__).parent.parent))

from runtime.lock_manager import LockManager

# In a real environment, this path is derived from the project structure.
workspace = Path(__file__).parent.parent
manager = LockManager(str(workspace))

TARGET = "brain/layer2_core/test.md"


def worker(agent_id: str):
    print(f"[{agent_id}] Attempting to acquire lock for {TARGET}...")

    # Simple acquire vs wait_and_acquire demonstration
    # Using wait_and_acquire allows the agent to spin-wait for a bit
    lock_id = manager.wait_and_acquire(agent_id, TARGET, ttl=5, timeout=3)

    if lock_id:
        print(f"✅ [{agent_id}] ACQUIRED lock: {lock_id}. Simulating LLM reasoning (2s)...")
        time.sleep(2)

        # Simulate successful finish and release
        if manager.release(agent_id, lock_id, TARGET):
            print(f"🔓 [{agent_id}] RELEASED lock.")
        else:
            print(f"⚠️ [{agent_id}] FAILED to release lock.")
    else:
        print(f"❌ [{agent_id}] FAILED to acquire lock. Another agent is holding it.")


if __name__ == "__main__":
    print(f"Starting Concurrency Test (Agent A vs Agent B) on {TARGET}\n")

    p1 = multiprocessing.Process(target=worker, args=("worker_A",))
    p2 = multiprocessing.Process(target=worker, args=("worker_B",))

    # Start them at almost exactly the same time to force a race condition
    p1.start()
    p2.start()

    p1.join()
    p2.join()

    print("\nTest completed.")
