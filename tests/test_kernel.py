import pytest
from kit.core.kernel import compute_state_vector
from kit.core.state_vector import StateVector

def test_grounding_state_vector():
    """
    Verify that the v1.2.4 kernel correctly hydrates a StateVector.
    This is the grounding point for the absolute physical reality of the brain.
    """
    mock_db_row = {
        "symbol": "kit.core.kernel.compute_state_vector",
        "structural_hash": "a1b2c3d4e5f6",
        "access_count": 42,
        "created_at": "2026-04-13T23:28:00Z",
        "is_baked": 1
    }

    sv = compute_state_vector(mock_db_row)

    assert isinstance(sv, StateVector)
    assert sv.symbol == "kit.core.kernel.compute_state_vector"
    assert sv.structural_hash == "a1b2c3d4e5f6"
    assert sv.access_count == 42
    assert sv.last_updated == "2026-04-13T23:28:00Z"
    assert sv.is_baked is True

def test_grounding_unbaked_state():
    """Verify handling of unbaked perception (is_baked=0)."""
    mock_row = {"symbol": "new_symbol", "is_baked": 0}
    sv = compute_state_vector(mock_row)
    assert sv.is_baked is False
    assert sv.structural_hash is None
