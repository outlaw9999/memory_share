import pytest
from kit.core.kernel import compute_state_vector

def test_unverified_graduation_block():
    """
    ADVERSARIAL: Prove that the Firewall prevents spoofed graduation.
    Expected: Kernel MUST downgrade is_baked=1 to 0 if agent is untrusted.
    """
    malicious_row = {
        "symbol": "kit_ecl",
        "structural_hash": "SPOOFED_HASH",
        "is_baked": 1, 
        "access_count": 1,
        "agent_id": "junior_bot" # Unauthorized
    }
    
    vector = compute_state_vector(malicious_row)
    
    # Verify the Firewall downgraded the status
    assert vector.is_baked is False, "Firewall failed to downgrade spoofed graduation status."
    
    # Re-verify with a trusted agent
    trusted_row = {
        "symbol": "kit_ecl",
        "structural_hash": "STABLE_HASH",
        "is_baked": 1,
        "access_count": 1,
        "agent_id": "senior" # Authorized match
    }
    vector_trusted = compute_state_vector(trusted_row)
    assert vector_trusted.is_baked is True, "Firewall blocked a trusted authority by mistake."
