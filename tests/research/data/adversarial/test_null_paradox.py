import pytest
import math
from kit.core.kernel import compute_state_vector

def test_null_garbage_robustness():
    """
    ADVERSARIAL: Prove that the Sanitizer prevents garbage leakage.
    Expected: Kernel falls back to safe defaults on NaN/Null/Negative.
    """
    garbage_row = {
        "symbol": None,
        "structural_hash": float('nan'),
        "access_count": -999,
        "is_baked": "GARBAGE" 
    }
    
    # Process through the hardened kernel
    vector = compute_state_vector(garbage_row)
    
    # Verify Sanitization Engine caught them
    assert vector.symbol == "anonymous", "Kernel didn't sanitize NULL symbol to 'anonymous'."
    assert vector.structural_hash is None, "Kernel leaked NaN instead of None."
    assert vector.access_count == 0, "Kernel didn't clamp negative access_count."
    assert vector.is_baked is False, "Kernel allowed garbage is_baked value."
