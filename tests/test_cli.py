import subprocess
import pytest
from pathlib import Path

def run_kit(*args):
    """Helper to run the kit CLI."""
    cmd = ["python", "kit.py"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result

def test_cli_lifecycle(tmp_path):
    # Use a temporary DB for the CLI test
    db_path = tmp_path / "cli_test.db"
    
    # In kit.py, we might need to point to this DB. 
    # For now, let's assume kit.py looks for brain.db in .kit/ or uses defaults.
    # Since we can't easily change the DB path via CLI yet (unless implemented), 
    # we'll test the default behavior or mock the environment if possible.
    
    # 1. Learn
    res = run_kit("learn", "--uid", "cli_node", "--content", "CLI test fact", "--importance", "0.7")
    assert res.returncode == 0
    
    # 2. Recall
    res = run_kit("recall", "cli_node")
    assert res.returncode == 0
    assert "CLI test fact" in res.stdout
    
    # 3. Search
    res = run_kit("search", "CLI")
    assert res.returncode == 0
    assert "CLI test fact" in res.stdout

def test_cli_context_generation():
    # Verify 'kit context' generates the manifests
    res = run_kit("context")
    assert res.returncode == 0
    assert Path("AGENTS.md").exists()
    assert Path(".kit/context").exists()
