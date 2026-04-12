import time

import pytest

from kit.core.kit_cognitive_core import SAMBrain
from kit.core.kit_reflect import ReflectReport, extract_signals, run_reflect


def test_extract_signals():
    diff = """
+ import requests
+ from numpy import array
+ require('stripe')
+ use std::collections::HashMap;
+ extern crate rocket;
- old_import
    """
    signals = extract_signals(diff)
    assert "requests" in signals
    assert "numpy" in signals
    assert "stripe" in signals
    assert "std" in signals  # In Rust 'std' is the root if using 'use std::...'
    assert "rocket" in signals
    assert "old_import" not in signals


def test_reflect_gap(tmp_path):
    db_path = tmp_path / "test_reflect.db"
    brain = SAMBrain(db_path)
    
    diff = "+ import requests"
    report = run_reflect(brain, diff, scope="test")
    
    assert "requests" in report.gaps
    assert report.score < 1.0


def test_reflect_drift(tmp_path):
    db_path = tmp_path / "test_reflect.db"
    brain = SAMBrain(db_path)
    
    # Learn fact in 'auth' scope
    brain.learn("requests", "infra", "Using requests in auth", scope="auth")
    
    # Reflect in 'payment' scope - different scope tree should trigger drift if margin is low
    diff = "+ import requests"
    report = run_reflect(brain, diff, scope="payment")
    
    assert "requests" in report.drifts


def test_reflect_violation(tmp_path):
    db_path = tmp_path / "test_reflect.db"
    brain = SAMBrain(db_path)
    
    # Learn global invariant (forbidden)
    brain.learn("forbidden_lib", "infra", "DO NOT USE", tag="invariant", scope="global")
    # Learn a local decision that tries to use it
    brain.learn("forbidden_lib", "infra", "Use it anyway", tag="decision", scope="auth")
    
    diff = "+ import forbidden_lib"
    report = run_reflect(brain, diff, scope="auth")
    
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
    assert duration_ms < 100  # Adjusted for CI overhead, target is < 50ms locally
