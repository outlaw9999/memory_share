import pytest
from kit.core.kernel import compute_state_vector

def test_signal_storm_inconsistency_block():
    """
    ADVERSARIAL: Prove that the kernel detects signal conflict.
    Expected: conflict_ratio > 0 if history contains mismatched hashes.
    """
    conflicting_signals = [
        {"symbol": "kit_ecl", "structural_hash": "HASH_A", "access_count": 1},
        {"symbol": "kit_ecl", "structural_hash": "HASH_B", "access_count": 2},
        {"symbol": "kit_ecl", "structural_hash": "HASH_A", "access_count": 3},
    ]
    
    # Process with history context
    vector = compute_state_vector(conflicting_signals[-1], history=conflicting_signals)
    
    # Verify conflict detection
    # most_common = HASH_A (2/3), so conflict = 1 - 2/3 = 0.33
    assert vector.conflict_ratio > 0, "Kernel failed to detect structural conflict in signal storm."
    assert 0.3 < vector.conflict_ratio < 0.4, "Conflict ratio calculation is incorrect."
