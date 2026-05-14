# tests/contract/test_memory_policy.py

import pytest
from tests.harness.policy_runner import PolicyTestHarness

def test_golden_truth_contracts():
    """
    ENFORCEMENT: All golden truth cases must pass.
    This locks the behavioral contract of Kit v1.2.5.
    """
    dataset_path = "e:/DEV/opensource_contrib/memory_share_kit/tests/golden/golden_memory_cases.jsonl"
    results = PolicyTestHarness.run_golden_suite(dataset_path)
    
    failures = [r for r in results if not r["pass"]]
    
    if failures:
        msg = "\n".join([f"FAIL {f['id']} [{f['intent']}]: Actual {f['actual_tier']}/{f['actual_content']}" for f in failures])
        pytest.fail(f"Golden Truth Contract Violated:\n{msg}")

def test_determinism_invariant():
    """
    INVARIANT: Repeated resolutions must yield identical results.
    """
    from kit.core.memory_policy import MemoryPolicy
    mock_memories = [
        type('M', (object,), {"brain_source": "local", "content": "A", "confidence": 0.5})(),
        type('M', (object,), {"brain_source": "local", "content": "B", "confidence": 0.5})()
    ]
    
    res1 = MemoryPolicy.resolve(mock_memories)
    res2 = MemoryPolicy.resolve(mock_memories)
    
    assert res1 == res2
    assert res1.content == "A" # Based on internal sort order
