import os
import re
from pathlib import Path


def test_single_connect_authority():
    """
    CRITICAL: Enforce Single-Authority Architecture.
    No module except 'memory_topology.py' is allowed to call sqlite3.connect().
    """
    project_root = Path(__file__).parents[1] / "kit"
    violations = []

    # Files allowed to use sqlite3 directly
    WHITELIST = {
        "memory_topology.py",
        # Phase C: ABI Lock exceptions
        "kit_lock.py",  # Uses connect for WAL checkpoint (administrative)
        "kit_cognitive_core.py",  # Uses connect for read-only URI mode when sealed
    }

    # Match ANY connect(...) pattern (v1.2.4-STABILIZE-HARD)
    CONNECT_PATTERN = re.compile(
        r"""
        (?:
            sqlite3\.connect      |   # sqlite3.connect(...)
            \bconnect\s*\(        |   # connect(...)
            \w+\.connect\s*\(         # alias.connect(...)
        )
        """,
        re.VERBOSE,
    )

    for py_file in project_root.rglob("*.py"):
        if py_file.name in WHITELIST:
            continue

        content = py_file.read_text(encoding="utf-8", errors="ignore")
        
        # v1.2.4-TITANIUM: Strip comments to prevent false positives in documentation
        stripped_lines = []
        for line in content.splitlines():
            code_part = line.split("#")[0]
            stripped_lines.append(code_part)
        stripped_content = "\n".join(stripped_lines)
        
        matches = CONNECT_PATTERN.findall(stripped_content)

        # Filter out authorized calls to our topology wrapper
        # We allow: topology.connect, self.topology.connect, _topo.connect
        unauthorized = []
        for m in matches:
            if ".connect" in m:
                if not any(token in m for token in ["topology.connect", "_topo.connect", "self.topology.connect", ".connect_path"]):
                    unauthorized.append(m)
            else:
                unauthorized.append(m)

        if unauthorized:
            violations.append(f"{py_file.relative_to(project_root.parent)} (matches: {unauthorized})")

    assert not violations, (
        "ARCHITECTURE VIOLATION:\n"
        "Unauthorized DB connect detected (Only MemoryTopology is the Authority):\n" + "\n".join(violations)
    )


def test_topology_naming_determinism():
    """Ensure naming conventions for 3-tier memory are locked."""
    from kit.core.memory_topology import MemoryTopology

    # We don't need a real project root for naming check
    topo = MemoryTopology(project_root=Path("C:/MockRepo"))

    assert topo.DB_LOCAL == "local_brain.db"
    assert topo.DB_GLOBAL == "global_brain.db"
    assert topo.DB_FROZEN == "global_read_only.db"
    assert topo.DB_ROUTING_AUDIT == "router_decisions.jsonl"
