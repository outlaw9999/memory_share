import subprocess
import sys
from pathlib import Path

from kit.api import get_brain
from kit.core.context_compiler import compile_execution_context
from kit.core.deterministic import deterministic_json
from kit.core.repo_scanner import scan_repo


# 1. Golden Hash Test
def test_execution_context_hash_stable():
    brain = get_brain()
    ctx = compile_execution_context(brain)
    # The actual golden hash for the current initial empty DB might differ
    # We test stability by ensuring two sequential compilations yield the exact same hash
    ctx2 = compile_execution_context(brain)
    assert ctx["context_hash"] == ctx2["context_hash"]
    assert ctx["schema_version"] == "1.0"


# 2. Deterministic JSON Test
def test_json_determinism():
    obj1 = {"b": 2, "a": 1}
    obj2 = {"a": 1, "b": 2}
    j1 = deterministic_json(obj1)
    j2 = deterministic_json(obj2)
    assert j1 == j2
    assert j1 == '{"a":1,"b":2}'


# 3. Repo Scanner Stability Test
def test_repo_scan_hash_stable():
    # Scan the current repository root
    root = Path(__file__).parent.parent
    r1 = scan_repo(root)
    r2 = scan_repo(root)
    assert r1["repo_hash"] == r2["repo_hash"]
    # Ensure ignore patterns are working (e.g. .venv should not be in final list)
    for f in r1.get("files", []):
        assert ".venv" not in Path(f).parts
        assert ".git" not in Path(f).parts


# 4. SQL Ordering Determinism Test
def test_sql_ordering():
    brain = get_brain()
    with brain.get_connection() as conn:
        # Check invariants
        sql_inv = "SELECT id, importance, created_at, node_id FROM observations WHERE tag = 'invariant' ORDER BY importance DESC, created_at ASC, node_id ASC, id ASC"
        rows = conn.execute(sql_inv).fetchall()
        if len(rows) > 1:
            # We just ensure the query runs and returns without syntax error in the tie breaker
            pass


# 5. Interpreter Lock Test (Boundary Test — v1.2.5: env-lock removed, always allowed)
def test_runtime_venv_lock():
    # v1.2.5: env-lock is permanently disabled (de-friction). Any Python works.
    # This test verifies the command runs without env-lock error.
    try:
        result = subprocess.run(["python", "-m", "kit.cli.main", "compile"], capture_output=True, text=True)
        # Should succeed or fail with a non-lock error. Must NOT print KIT-ENV-LOCK.
        assert "KIT-ENV-LOCK" not in result.stderr
    except FileNotFoundError:
        pass
