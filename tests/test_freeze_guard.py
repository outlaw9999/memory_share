import json
from pathlib import Path

import pytest

from kit.core.kit_cognitive_core import Memory
from kit.core.memory_policy import MemoryPolicy


def load_golden_data():
    path = Path(__file__).parent / "golden_arbitration.json"
    with open(path) as f:
        return json.load(f)


@pytest.mark.parametrize("case", load_golden_data()["cases"])
def test_freeze_guard(case):
    """
    ARCHITECTURAL FREEZE GUARD: Enforces that Kit 1.2.5 arbitration logic
    never drifts from the certified Golden Truth.
    """
    pool_data = case["pool"]
    pool = [
        Memory(
            id=m["id"],
            node_uid=f"node:{m['id']}",
            content=m["content"],
            score=m["score"],
            brain_source=m["brain_source"],
            created_at=m["created_at"],
        )
        for m in pool_data
    ]

    # We use a fixed 'now' for the test cases if needed,
    # but the cases use absolute created_at strings.
    import time

    now = time.time()

    winner = MemoryPolicy.resolve(pool, now=now)

    # [1.2.5IMMUTABLE] Binary Verification: Winner must be bit-identical
    assert winner.id == case["expected_id"], (
        f"FREEZE VIOLATION in '{case['name']}': "
        f"Expected ID {case['expected_id']}, but got {winner.id}. "
        f"Reason: {case['reason']}"
    )


def test_policy_integrity_lock():
    """Ensures the source code of MemoryPolicy has not drifted (SHA256)."""
    import hashlib

    import kit.core.memory_policy as mp

    path = Path(mp.__file__)

    from kit.core.kit_ledger import get_certified_hash
    
    expected_hash = get_certified_hash("kit/core/memory_policy.py")
    
    if not expected_hash:
        # Fallback to legacy lock file
        lock_path = path.parent / "memory_policy.lock"
        if lock_path.exists():
            with open(lock_path) as f:
                expected_hash = f.read().strip()
    
    assert expected_hash, "No certified hash found in ledger or legacy lock file."


    with open(path, "rb") as f:
        current_hash = hashlib.sha256(f.read()).hexdigest()

    assert current_hash == expected_hash, (
        f"INTEGRITY VIOLATION: MemoryPolicy source has been modified!\n"
        f"Expected: {expected_hash}\n"
        f"Actual:   {current_hash}"
    )


def test_policy_version_lock():
    """Ensures the policy is explicitly marked as FROZEN."""
    assert hasattr(MemoryPolicy, "POLICY_VERSION"), "MemoryPolicy must have a POLICY_VERSION."
    assert MemoryPolicy.POLICY_VERSION == "1.2.5", "Policy version drift detected!"


if __name__ == "__main__":
    pytest.main([__file__])
