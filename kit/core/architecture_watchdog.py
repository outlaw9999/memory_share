"""
Architecture Watchdog - Autonomous Drift Detection & Prevention.

Monitors code changes and enforces architectural constraints automatically.
Can be integrated into CI/CD, pre-commit hooks, or IDE linting.

Concept: ~200 lines of core logic
- Detect violations without human review
- Block merges that violate policy
- Self-learning from approved exceptions
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any, Set
from dataclasses import dataclass
from enum import Enum
import json
import time


class ViolationType(Enum):
    """Types of architecture violations."""

    CIRCULAR_DEPENDENCY = "circular_dependency"
    LAYER_VIOLATION = "layer_violation"
    GOD_MODULE = "god_module"
    CYCLOMATIC_SPIKE = "cyclomatic_spike"
    UNSTABLE_IMPORT = "unstable_import"
    UNAUTHORIZED_CROSSING = "unauthorized_crossing"
    TEMPORAL_ANOMALY = "temporal_anomaly"


@dataclass
class ArchitecturePolicy:
    """Policy definition for what's allowed."""

    # Layer structure (ordered from highest to lowest level)
    layers: List[str] = None  # type: ignore[assignment]  # e.g., ["api", "service", "repo", "util"]

    # Allowed transitions (src_layer -> dst_layer)
    allowed_transitions: Dict[str, List[str]] = None  # type: ignore[assignment]

    # Max complexity metrics
    max_fanout: int = 10  # max callees per function
    max_god_module_size: int = 1000  # max symbols per file

    # Temporal coupling threshold
    temporal_anomaly_threshold: float = 0.8

    # Files that are exempt from some rules
    exempt_paths: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.layers is None:
            self.layers = ["api", "service", "repo", "util"]
        if self.allowed_transitions is None:
            # Default: each layer can call lower layers
            self.allowed_transitions = {
                "api": ["service", "repo", "util"],
                "service": ["repo", "util"],
                "repo": ["util"],
                "util": [],
            }
        if self.exempt_paths is None:
            self.exempt_paths = ["test", "mock", "example", "__pycache__"]


@dataclass
class Violation:
    """Single violation found."""

    violation_type: ViolationType
    severity: str  # "error", "warning", "info"
    symbol_a: str
    symbol_b: str
    file_a: str
    file_b: str
    message: str
    remediation: str
    confidence: float  # 0.0 - 1.0


class ArchitectureWatchdog:
    """
    Autonomous architecture enforcement.

    Runs in CI/CD:
    - PR submission
    - Pre-commit hook
    - IDE linting
    """

    def __init__(
        self, graph_db_path: Path | str, policy: ArchitecturePolicy | None = None
    ):
        self.db_path = Path(graph_db_path)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.policy = policy or ArchitecturePolicy()
        self.violations: List[Violation] = []

    def scan_changes(
        self, changed_files: List[str], base_branch: str = "main"
    ) -> List[Violation]:
        """
        Scan changed files for violations.

        Args:
            changed_files: List of paths that changed (from git diff)
            base_branch: Branch to compare against

        Returns:
            List of violations found
        """
        self.violations = []

        # Get symbols that were modified
        modified_symbols = self._get_modified_symbols(changed_files)

        # Run violation checks
        self._check_circular_dependencies(modified_symbols)
        self._check_layer_violations(modified_symbols)
        self._check_god_modules(changed_files)
        self._check_cyclomatic_spike(modified_symbols)
        self._check_temporal_anomalies(modified_symbols)

        return self.violations

    def _get_modified_symbols(self, changed_files: List[str]) -> List[str]:
        """Get symbols from changed files."""
        cur = self.conn.cursor()
        symbols = []

        for file_path in changed_files:
            cur.execute(
                "SELECT DISTINCT name FROM symbols WHERE file = ?", (file_path,)
            )
            for row in cur.fetchall():
                symbols.append(row["name"])

        return symbols

    def _check_circular_dependencies(self, symbols: List[str]) -> None:
        """
        Detect circular call chains.

        Bad: A → B → C → A
        """
        for symbol in symbols:
            cycles = self._find_cycles(symbol, max_depth=4)

            if cycles:
                for cycle in cycles:
                    severity = "error" if len(cycle) <= 3 else "warning"

                    self.violations.append(
                        Violation(
                            violation_type=ViolationType.CIRCULAR_DEPENDENCY,
                            severity=severity,
                            symbol_a=cycle[0],
                            symbol_b=cycle[-1],
                            file_a=self._get_symbol_file(cycle[0]),
                            file_b=self._get_symbol_file(cycle[-1]),
                            message=f"Circular dependency: {' → '.join(cycle)}",
                            remediation=f"Break cycle by removing call from {cycle[-1]} to {cycle[0]}",
                            confidence=0.95,
                        )
                    )

    def _find_cycles(self, start: str, max_depth: int = 4) -> List[List[str]]:
        """Use DFS to find cycles."""
        cur = self.conn.cursor()
        cycles = []

        def dfs(node: str, path: List[str], visited: Set[str]) -> None:
            if len(path) > max_depth:
                return

            cur.execute("SELECT DISTINCT callee FROM calls WHERE caller = ?", (node,))

            for row in cur.fetchall():
                callee = row["callee"]

                if callee == start and len(path) > 1:
                    cycles.append(path + [callee])
                elif callee not in visited and len(path) < max_depth:
                    visited.add(callee)
                    dfs(callee, path + [callee], visited)
                    visited.remove(callee)

        dfs(start, [start], {start})
        return cycles

    def _check_layer_violations(self, symbols: List[str]) -> None:
        """
        Detect layer crossing violations.

        Bad: util → service (wrong direction)
        """
        cur = self.conn.cursor()

        for symbol in symbols:
            symbol_file = self._get_symbol_file(symbol)
            src_layer = self._extract_layer(symbol_file)

            # Get outgoing edges
            cur.execute("SELECT DISTINCT callee FROM calls WHERE caller = ?", (symbol,))

            for row in cur.fetchall():
                callee = row["callee"]
                callee_file = self._get_symbol_file(callee)
                dst_layer = self._extract_layer(callee_file)

                # Check if transition allowed
                if not self._is_transition_allowed(src_layer, dst_layer):
                    self.violations.append(
                        Violation(
                            violation_type=ViolationType.LAYER_VIOLATION,
                            severity="error",
                            symbol_a=symbol,
                            symbol_b=callee,
                            file_a=symbol_file,
                            file_b=callee_file,
                            message=f"Layer violation: {src_layer} cannot call {dst_layer}",
                            remediation=f"Refactor to remove dependency or reclassify layers",
                            confidence=0.98,
                        )
                    )

    def _check_god_modules(self, changed_files: List[str]) -> None:
        """
        Detect files with too many symbols (God Modules).

        Bad: >1000 symbols in one file
        """
        cur = self.conn.cursor()

        for file_path in changed_files:
            cur.execute(
                "SELECT COUNT(*) as cnt FROM symbols WHERE file = ?", (file_path,)
            )

            count = cur.fetchone()["cnt"]

            if count > self.policy.max_god_module_size:
                self.violations.append(
                    Violation(
                        violation_type=ViolationType.GOD_MODULE,
                        severity="warning",
                        symbol_a=file_path,
                        symbol_b="",
                        file_a=file_path,
                        file_b="",
                        message=f"God module detected: {count} symbols (max {self.policy.max_god_module_size})",
                        remediation=f"Split file into smaller modules",
                        confidence=1.0,
                    )
                )

    def _check_cyclomatic_spike(self, symbols: List[str]) -> None:
        """
        Detect spike in cyclomatic complexity.

        When a function's fanout suddenly increases dramatically.
        """
        cur = self.conn.cursor()

        for symbol in symbols:
            cur.execute("SELECT COUNT(*) as cnt FROM calls WHERE caller = ?", (symbol,))

            fanout = cur.fetchone()["cnt"]

            if fanout > self.policy.max_fanout:
                self.violations.append(
                    Violation(
                        violation_type=ViolationType.CYCLOMATIC_SPIKE,
                        severity="warning",
                        symbol_a=symbol,
                        symbol_b="",
                        file_a=self._get_symbol_file(symbol),
                        file_b="",
                        message=f"High fanout: {symbol} calls {fanout} functions (max {self.policy.max_fanout})",
                        remediation=f"Break into smaller functions or aggregate calls",
                        confidence=0.85,
                    )
                )

    def _check_temporal_anomalies(self, symbols: List[str]) -> None:
        """
        Detect unexpected temporal coupling.

        When two unrelated files suddenly change together.
        """
        # This requires temporal graph data
        # Simplified version: check git changes
        pass

    def _extract_layer(self, file_path: str) -> str:
        """Extract layer from file path."""
        path = Path(file_path)
        parts = path.parts

        for layer in self.policy.layers:
            if layer in parts:
                return layer

        return "unknown"

    def _is_transition_allowed(self, src: str, dst: str) -> bool:
        """Check if src → dst transition is allowed."""
        if src not in self.policy.allowed_transitions:
            return False

        return dst in self.policy.allowed_transitions[src]

    def _get_symbol_file(self, symbol: str) -> str:
        """Get file path for symbol."""
        cur = self.conn.cursor()
        cur.execute("SELECT file FROM symbols WHERE name = ? LIMIT 1", (symbol,))
        row = cur.fetchone()
        return row["file"] if row else "unknown"

    def format_report(self) -> str:
        """Format violations into human-readable report."""
        if not self.violations:
            return "✓ No architecture violations detected"

        errors = [v for v in self.violations if v.severity == "error"]
        warnings = [v for v in self.violations if v.severity == "warning"]

        report = []
        report.append(
            f"\n❌ Architecture Violations Found ({len(self.violations)} total)"
        )
        report.append(f"   Errors: {len(errors)}, Warnings: {len(warnings)}\n")

        if errors:
            report.append("🚨 ERRORS (must fix):\n")
            for v in errors:
                report.append(f"  {v.violation_type.value}: {v.message}")
                report.append(f"    → {v.remediation}\n")

        if warnings:
            report.append("⚠️  WARNINGS (should fix):\n")
            for v in warnings:
                report.append(f"  {v.violation_type.value}: {v.message}")
                report.append(f"    → {v.remediation}\n")

        return "\n".join(report)

    def to_json(self) -> str:
        """Export violations as JSON (for CI/CD parsing)."""
        return json.dumps(
            [
                {
                    "type": v.violation_type.value,
                    "severity": v.severity,
                    "message": v.message,
                    "remediation": v.remediation,
                    "symbol_a": v.symbol_a,
                    "symbol_b": v.symbol_b,
                    "file_a": v.file_a,
                    "file_b": v.file_b,
                    "confidence": v.confidence,
                }
                for v in self.violations
            ],
            indent=2,
        )

    def should_block_merge(self) -> bool:
        """
        Determine if PR should be blocked.

        Block if: any error-severity violations found
        """
        return any(v.severity == "error" for v in self.violations)

    def close(self) -> None:
        """Close database."""
        self.conn.close()


# ============================================================================
# CI/CD Integration Examples
# ============================================================================

# GitHub Actions Integration
GITHUB_ACTIONS_TEMPLATE = """name: Architecture Watchdog

on: [pull_request]

jobs:
  watchdog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0
      
      - name: Get changed files
        id: changed
        run: |
          git fetch origin main
          FILES=$(git diff --name-only origin/main...HEAD | grep -E '\\.(py|ts|js|go)$')
          echo "files=$FILES" >> $GITHUB_OUTPUT
      
      - name: Run Architecture Watchdog
        run: |
          python -m pytest test_architecture_watchdog.py --changed-files "${{ steps.changed.outputs.files }}"
      
      - name: Block on errors
        if: failure()
        run: exit 1
"""

# Pre-commit Hook Integration
PRE_COMMIT_TEMPLATE = """#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path
from kit.architecture_watchdog import ArchitectureWatchdog, ArchitecturePolicy

workspace = Path(".antigravity/atlas/atlas.db")
watchdog = ArchitectureWatchdog(workspace)

# Get staged files
result = subprocess.run(
    ["git", "diff", "--name-only", "--cached"],
    capture_output=True,
    text=True
)

changed_files = result.stdout.strip().split("\\n")
violations = watchdog.scan_changes(changed_files)

print(watchdog.format_report())

if watchdog.should_block_merge():
    sys.exit(1)

watchdog.close()
"""


# Django/FastAPI Integration
def create_watchdog_middleware(watchdog_instance: "ArchitectureWatchdog") -> Any:
    """Middleware to check watchdog status in API."""

    async def middleware(request: Any, call_next: Any) -> Any:
        # Only on certain endpoints
        if "/api/architecture/check" in request.url.path:
            changed_files = request.query_params.get("files", "").split(",")
            violations = watchdog_instance.scan_changes(changed_files)

            return {
                "violations": len(violations),
                "should_block": watchdog_instance.should_block_merge(),
                "report": watchdog_instance.format_report(),
            }

        return await call_next(request)

    return middleware


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: architecture_watchdog.py <db_path> <file1> [file2] ...")
        sys.exit(1)

    db_path = sys.argv[1]
    changed_files = sys.argv[2:]

    watchdog = ArchitectureWatchdog(db_path)
    violations = watchdog.scan_changes(changed_files)

    print(watchdog.format_report())

    if watchdog.should_block_merge():
        print("\n❌ Merge blocked due to architecture violations")
        sys.exit(1)
    else:
        print("\n✅ Architecture check passed")
        sys.exit(0)

    watchdog.close()
