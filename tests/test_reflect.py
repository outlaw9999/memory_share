import time
import pytest
from kit.core.kit_cognitive_core import SAMBrain
from kit.core.kit_reflect import run_reflect, extract_signals, ReflectReport

def test_extract_signals():
    diff = """
+ import os
+ from pathlib import Path
+ require('stripe')
+ use std::collections::HashMap;
+ extern crate rocket;
- old_import
    """
    signals = extract_signals(diff)
    assert "os" in signals
    assert "pathlib" in signals
    assert "stripe" in signals
    assert "std::collections::HashMap" in signals
    assert "rocket" in signals
    assert "old_import" not in signals

def test_reflect_gap(tmp_path):
    db_path = tmp_path / "test_reflect.db"
    brain = SAMBrain(db_path)
    
    diff = "+ import new_lib"
    report = run_reflect(brain, diff, scope="test")
    
    print(f"\nDEBUG test_reflect_gap: Gaps={report.gaps}, Drifts={report.drifts}, Violations={report.violations}")
    assert "new_lib" in report.gaps
    assert report.status == "WARN"
    assert report.score < 1.0

def test_reflect_drift(tmp_path):
    db_path = tmp_path / "test_reflect.db"
    brain = SAMBrain(db_path)
    
    # Learn fact in 'auth' scope
    brain.learn("lib", "infra", "Using lib in auth", scope="auth")
    
    # Reflect in 'payment' scope
    diff = "+ import lib"
    report = run_reflect(brain, diff, scope="payment")
    
    assert "lib" in report.drifts
    assert "lib" not in report.gaps

def test_reflect_violation(tmp_path):
    db_path = tmp_path / "test_reflect.db"
    brain = SAMBrain(db_path)
    
    # Learn invariant
    brain.learn("forbidden_lib", "infra", "DO NOT USE THIS LIB", tag="invariant")
    
    diff = "+ import forbidden_lib"
    report = run_reflect(brain, diff, scope="any")
    
    assert "forbidden_lib" in report.violations
    assert report.status == "BLOCK"

def test_reflect_performance(tmp_path):
    db_path = tmp_path / "test_reflect.db"
    brain = SAMBrain(db_path)
    
    # Populate brain with some noise
    for i in range(100):
        brain.learn(f"node_{i}", "node", f"Content {i}")
        
    diff = "\n".join([f"+ import lib_{i}" for i in range(50)])
    
    start = time.perf_counter()
    run_reflect(brain, diff, scope="test")
    end = time.perf_counter()
    
    duration_ms = (end - start) * 1000
    print(f"\nReflection Performance: {duration_ms:.2f}ms")
    assert duration_ms < 100 # Adjusted for CI overhead, target is < 50ms locally
