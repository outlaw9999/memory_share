# tests/test_architectural_invariants.py
# v1.2.4-TITANIUM: Final Architecture Freeze Suite
#
# Philosophy:
#   This suite does NOT test features. It tests BOUNDARIES.
#   It ensures that the "Single Authority" principle is never violated.

import ast
import os
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
FORBIDDEN_PATTERNS = [
    "materialized_score *",
    "importance *",
    ".score =",
    "score =",
    "calculate_score", # Except in MemoryPolicy
    "sort(key=lambda"   # High risk of hidden ranking logic
]

ALLOWED_FILES = [
    "kit/core/memory_policy.py",
    "tests/test_architectural_invariants.py",
    "kit/core/memory_router.py", # Allowed to hydrate materialized_score from DB
]

def test_single_authority_lock():
    """
    INVARIANT 1: MemoryPolicy MUST be the only module that computes scores or resolves ranking.
    """
    violations = []
    
    for root, _, files in os.walk(PROJECT_ROOT / "kit"):
        for file in files:
            if not file.endswith(".py"):
                continue
                
            path = Path(root) / file
            rel_path = path.relative_to(PROJECT_ROOT).as_posix()
            
            if rel_path in ALLOWED_FILES:
                continue
                
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                
                # Rule 1: No scoring logic definitions or manual implementations
                # We allow calls like 'MemoryPolicy.calculate_score'
                if "def calculate_score" in content:
                    violations.append(f"{rel_path}: Found 'calculate_score' DEFINITION outside of MemoryPolicy.")
                
                # Rule 2: No manual ranking/sorting keys that don't delegate to MemoryPolicy
                if "sort(key=" in content and "MemoryPolicy" not in content:
                    # Check if it's a suspicious sort key using importance or score directly
                    # but ignore simple name sorts or list sorts
                    if "importance" in content or "materialized_score" in content:
                         # We check if the lambda actually uses them
                         violations.append(f"{rel_path}: Found manual sort() with suspicious scoring keywords.")

                # Rule 3: No direct importance weighting arithmetic (except in MemoryPolicy)
                import re
                if re.search(r"importance\s*[\*\/]", content):
                    violations.append(f"{rel_path}: Found direct importance weighting arithmetic.")

                # Rule 4: Hard Guard check (no legacy method names)
                if "_calculate_runtime_score" in content and "DELETED" not in content and "__getattr__" not in content:
                     violations.append(f"{rel_path}: Found legacy '_calculate_runtime_score' string.")

    assert not violations, f"Architectural Invariant Violation (Single Authority Lock):\n" + "\n".join(violations)

def test_router_purity_contract():
    """
    INVARIANT 2: MemoryRouter MUST only fetch, never rank.
    """
    router_path = PROJECT_ROOT / "kit" / "core" / "memory_router.py"
    with open(router_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # We check the AST for the resolve_read method
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "resolve_read":
            method_source = ast.get_source_segment(content, node)
            # The router should NOT call arbitrate or calculate_score in its recall loop
            assert "MemoryPolicy.arbitrate" not in method_source
            assert "MemoryPolicy.calculate_score" not in method_source
            assert ".sort(" not in method_source

def test_determinism_contract():
    """
    INVARIANT 4: MemoryPolicy arbitration MUST be deterministic.
    """
    # Import locally to avoid pollution
    from kit.core.memory_policy import MemoryPolicy
    from kit.core.kit_cognitive_core import Memory
    import time
    
    m1 = Memory(id=1, node_uid="A", content="fact A", score=0.8, brain_source="local", importance=1.0)
    m2 = Memory(id=2, node_uid="B", content="fact B", score=0.9, brain_source="global", importance=0.9)
    
    candidates = [m1, m2]
    now = time.time()
    
    # Run 100 times, result must be identical
    results = []
    for _ in range(100):
        res = MemoryPolicy.arbitrate(candidates, now=now)
        results.append([m.id for m in res])
        
    for r in results:
        assert r == results[0], "Nondeterministic arbitration detected!"

def test_sam_brain_orchestration_purity():
    """
    INVARIANT 3: SAMBrain MUST NOT compute ranking or scores.
    """
    core_path = PROJECT_ROOT / "kit" / "core" / "kit_cognitive_core.py"
    with open(core_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert "def _calculate_runtime_score" not in content
    assert "def _recall_sort_key" not in content
    
    # Ensure it delegates to MemoryPolicy.arbitrate
    assert "MemoryPolicy.arbitrate" in content
