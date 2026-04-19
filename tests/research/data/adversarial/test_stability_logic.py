import pytest
from kit.core.kernel import compute_state_vector

def test_stability_monotonicity_violation():
    """
    ADVERSARIAL: Prove that stability collapse triggers a BLOCK.
    Expected: stability_score < 0.2 MUST result in state="BLOCK".
    """
    # History of a symbol drifting wildly
    history = [
        {"symbol": "kit_ecl", "structural_hash": "A"},
        {"symbol": "kit_ecl", "structural_hash": "B"},
        {"symbol": "kit_ecl", "structural_hash": "C"},
        {"symbol": "kit_ecl", "structural_hash": "D"},
        {"symbol": "kit_ecl", "structural_hash": "E"}, # 5 unique hashes
    ]
    
    current_row = history[-1]
    vector = compute_state_vector(current_row, history=history)
    
    # Verify Identity Collapse
    # S_id = 1/5 = 0.2. (Borderline)
    # Let's add one more drift to cross the threshold.
    history.append({"symbol": "kit_ecl", "structural_hash": "F"})
    vector_collapsed = compute_state_vector(history[-1], history=history)
    
    # S_id = 1/6 = 0.166 < 0.2
    assert vector_collapsed.stability_score < 0.2, "Stability score calculation is incorrect."
    assert vector_collapsed.state == "BLOCK", "Kernel failed to block on identity collapse."
    assert vector_collapsed.reason == "IDENTITY_COLLAPSE", "Incorrect block reason."
    
    # Monotonicity check: score(History_3) <= score(History_2)
    # This logic will be added to kit_cmc later.
