import pytest
from kit.core.kit_cognitive_core import SAMBrain

@pytest.fixture
def brain(tmp_path):
    db_path = tmp_path / "test_search.db"
    return SAMBrain(db_path)

def test_search_signature_compat(brain):
    """
    Regression Test: Ensure SAMBrain.search accepts compatibility parameters.
    This prevents Interface Drift between api.py and kit_cognitive_core.py.
    """
    # Learn something to have content to search for
    brain.learn("test_uid", "Friction detected in the gears.", tag="friction")
    
    # Test with all arguments that api.py might pass
    # These should NOT raise TypeError
    results = brain.search(
        "friction",
        limit=5,
        agent_id="test_agent",
        at_timestamp="2026-04-19T00:00:00Z",
        fast=True
    )
    
    assert isinstance(results, list)
    assert len(results) > 0
    assert "Friction" in results[0].content
    assert results[0].tag == "friction"

def test_search_minimal_call(brain):
    """Ensure minimal call still works."""
    brain.learn("test_uid_2", "Normal behavior.", tag="decision")
    results = brain.search("Normal")
    assert len(results) > 0
    assert "Normal" in results[0].content
