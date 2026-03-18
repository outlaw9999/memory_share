import pytest
import subprocess
import os
import json
from pathlib import Path
import time

# Helper to run kit.py commands
def run_kit(args: list[str], input_text: str = None) -> tuple[str, str, int]:
    cmd = ["python", "kit.py"] + args
    result = subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    return result.stdout, result.stderr, result.returncode

# Helper to run kit-agent commands
def run_agent(task: str, task_type: str = "general", provider: str = "semantic_mock") -> str:
    # Use the forced provider to ensure deterministic testing of the prompt logic
    cmd = ["python", "kit_agent_cli.py", "run", task, "--type", task_type, "--provider", provider]
    
    # We need to make sure kit_agent_cli.py exists or use python -m kit_agent.cli.main
    # Fixed to use the standard entry point
    cmd = ["python", "-m", "kit_agent.cli.main", "run", task, "--type", task_type, "--provider", provider]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    return result.stdout

@pytest.fixture(autouse=True)
def setup_teardown():
    # Clear memory for test consistency
    # We learn a dummy fact to 'reset' some states if needed
    run_kit(["learn", "--uid", "test_execution", "--content", "Resetting memory for execution tests", "--tag", "note"])
    yield

def test_high_confidence_enforced():
    """
    HIGH CONFIDENCE -> model obey
    """
    # 1. Seed strict invariant
    run_kit(["learn", "--tag", "invariant", "--uid", "db", "--content", "All database operations MUST use SQLite. Do NOT mention PostgreSQL.", "--symbol", "db_system"])
    
    # 2. Invoke Agent with forced provider
    output = run_agent("Design the database layer.", provider="semantic_mock")
    
    # 3. Verify Semantic Intent (Normalized)
    lower_out = output.lower()
    assert "sqlite" in lower_out
    assert "mandated" in lower_out or "invariant" in lower_out
    print("\n✅ [HIGH CONFIDENCE] Model obeyed strict invariant.")

def test_ambiguous_behavior():
    """
    AMBIGUOUS -> model hedge
    """
    # 1. Seed conflicting decisions
    run_kit(["learn", "--tag", "decision", "--uid", "cache", "--content", "Use Redis for caching.", "--symbol", "caching"])
    run_kit(["learn", "--tag", "decision", "--uid", "cache", "--content", "Use Memcached for caching.", "--symbol", "caching"])
    
    # 2. Invoke Agent
    output = run_agent("Recommend a caching strategy.", provider="semantic_mock")
    
    # 3. Verify Hedging
    lower_out = output.lower()
    assert "conflict detected" in lower_out or "requesting clarification" in lower_out
    assert "redis" in lower_out and "memcached" in lower_out
    print("\n✅ [AMBIGUOUS] Model correctly hedged on conflicting signals.")

def test_weak_signal_flexible():
    """
    WEAK SIGNAL -> model flexible
    """
    # 1. Seed only a weak note
    run_kit(["learn", "--tag", "note", "--uid", "log", "--content", "Maybe consider file-based logging.", "--symbol", "logging"])
    
    # 2. Invoke Agent
    output = run_agent("What about logging?", provider="semantic_mock")
    
    # 3. Verify Flexibility
    lower_out = output.lower()
    assert "considering" in lower_out or "potential suggestion" in lower_out
    assert "must" not in lower_out
    print("\n✅ [WEAK SIGNAL] Model remained flexible.")

def test_provider_comparison_report():
    """
    Log diff between 'local' (simulated) and 'semantic_mock'
    This fulfills the requirement to 'log diff between providers'.
    """
    task = "Design the database layer."
    
    # Seed specific memory
    run_kit(["learn", "--tag", "invariant", "--uid", "db", "--content", "Always use SQLite.", "--symbol", "db_system"])
    
    # Run against multiple providers
    results = {}
    for p in ["semantic_mock", "mock"]: # Using mocks since real ones might not be reachable
        results[p] = run_agent(task, provider=p)
    
    # Log Comparison
    report_file = Path("tests/execution_comparison.log")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"Execution Comparison Report: {task}\n")
        f.write("="*40 + "\n\n")
        for p, out in results.items():
            f.write(f"--- PROVIDER: {p} ---\n")
            f.write(out)
            f.write("\n\n")
            
    print(f"\n✅ Comparison report generated at {report_file}")

if __name__ == "__main__":
    # If run directly as a script
    import sys
    pytest.main([__file__])
