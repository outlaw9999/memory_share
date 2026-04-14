import pytest
from kit.core.kernel import compute_state_vector
from kit.core.state_vector import StateVector

def test_force_identity_hijack_block():
    """
    ADVERSARIAL: Prove that the Identity Firewall blocks hijacking.
    Expected: Kernel MUST return state=BLOCK if structural_hash changes.
    """
    # Mock row representing an existing symbol in the brain (The Anchor)
    existing_state = {
        "symbol": "kit_ecl",
        "structural_hash": "OLD_STABLE_HASH",
        "access_count": 10,
        "is_baked": 1
    }
    
    # Simulate a new perception for the SAME symbol with a DIFFERENT hash
    new_perception = {
        "symbol": "kit_ecl",
        "structural_hash": "NEW_MALICIOUS_HASH",
        "access_count": 11,
        "is_baked": 1
    }
    
    # Hydrate vector WITH the anchor reference
    vector = compute_state_vector(new_perception, anchor_row=existing_state)
    
    # Verify the Firewall caught it
    assert vector.state == "BLOCK", "Firewall failed to block the identity hijack."
    assert vector.reason == "IDENTITY_MISMATCH", "Incorrect block reason."
    assert vector.severity == "HIGH", "Severity should be high for identity fraud."
