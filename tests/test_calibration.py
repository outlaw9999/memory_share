import pytest

from kit.core.kit_cognitive_core import SAMBrain
from kit.core.kit_reflect import run_reflect


def test_invariant_sanctity(tmp_path):
    """VERIFY: Global Invariant CANNOT be overridden by Local Decision."""
    db_path = tmp_path / "test_calibration.db"
    brain = SAMBrain(db_path)
    
    # Global Invariant
    brain.learn(uid="vantage", content="DO NOT USE VANTAGE DIRECTLY", tag="invariant", scope="")
    
    # Local Decision (higher importance but still below GLOBAL threshold)
    brain.learn(uid="vantage", content="Use vantage for auth", tag="decision", scope="auth", importance=0.3)
    
    diff = "+ import vantage"
    report = run_reflect(brain, diff, scope="auth")
    
    # Final verdict should be BLOCK
    assert report.status == "BLOCK"
    assert "vantage" in report.violations
    res = report.resolutions["vantage"]
    assert "CONSTITUTIONAL VIOLATION" in res.reason


def test_scoped_invariant_override(tmp_path):
    """VERIFY: Multiple Invariants conflict triggers BLOCK (Hard Governance)."""
    db_path = tmp_path / "test_calibration.db"
    brain = SAMBrain(db_path)
    
    # Global Invariant
    brain.learn(uid="db", content="Use PostgreSQL", tag="invariant", scope="")
    
    # Scoped Invariant (Allowing SQLite only in auth)
    brain.learn(uid="db", content="Use SQLite for auth", tag="invariant", scope="auth")
    
    diff = "+ import db"
    report = run_reflect(brain, diff, scope="auth")
    
    # In AMSB v1.1, conflicting invariants require supervised resolution
    assert report.status == "BLOCK"
    res = report.resolutions["db"]
    assert "CONSTITUTIONAL CONFLICT" in res.reason


def test_parent_vs_child_decision(tmp_path):
    """VERIFY: Child scope decision beats parent scope decision (Additive Scoring)."""
    db_path = tmp_path / "test_calibration.db"
    brain = SAMBrain(db_path)
    
    # Parent Decision (src)
    brain.learn(uid="logger", content="Use JSON logger", tag="decision", scope="src")
    
    # Child Decision (src/auth)
    brain.learn(uid="logger", content="Use Plain logger", tag="decision", scope="src/auth")
    
    diff = "+ import logger"
    report = run_reflect(brain, diff, scope="src/auth")
    
    assert report.status == "PASS"
    res = report.resolutions["logger"]
    assert "Plain logger" in res.winner_content
    assert "Scoped refinement wins" in res.reason


def test_confidence_margin(tmp_path):
    """VERIFY: Confidence reflects the margin between candidates."""
    db_path = tmp_path / "test_calibration.db"
    brain = SAMBrain(db_path)
    
    # Winner: exact match scope (+0.2 bonus)
    brain.learn(uid="test", content="Winner", scope="auth", tag="decision")
    # Loser: broader scope (+0.1 bonus)
    brain.learn(uid="test", content="Loser", scope="", tag="decision")
    
    diff = "+ import test"
    report = run_reflect(brain, diff, scope="auth")

    res = report.resolutions["test"]
    # v1.2.5-TITANIUM: Updated calibration for high-precision adaptive scoring
    assert 0.4 < res.confidence < 0.7
