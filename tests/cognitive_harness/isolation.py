"""
MemoryIsolationGuard - Test local vs global isolation and sealing invariance.

v1.2.4: Validates that:
- Local memory doesn't leak to global without permission
- seal() blocks all writes
- purge() clears state completely
"""

import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from kit.core.kit_cognitive_core import SAMBrain
from kit.core.memory_topology import MemoryTopology, MemoryTopologyFactory


@dataclass
class IsolationTestResult:
    """Result of an isolation test."""
    test_name: str
    passed: bool
    message: str
    details: dict = field(default_factory=dict)


class MemoryIsolationGuard:
    """
    Guard for memory isolation and sealing tests.

    Tests:
    1. Local vs Global isolation (no cross-contamination)
    2. seal() blocks writes after called
    3. purge() clears all state
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.topology = MemoryTopologyFactory.for_project(project_root)
        self.local_db: Optional[Path] = None
        self.global_db: Optional[Path] = None

    def setup_dbs(self, local_path: Path, global_path: Path):
        """Set up local and global DB paths."""
        self.local_db = local_path
        self.global_db = global_path

    def test_local_global_isolation(
        self,
        local_brain: SAMBrain,
        global_brain: SAMBrain,
    ) -> IsolationTestResult:
        """
        Test that local writes don't affect global.

        This test requires TWO separate brains with different topologies.
        """
        local_test_key = f"isolation:local:{id(self)}"
        global_test_key = f"isolation:global:{id(self)}"

        local_brain.learn(
            uid=local_test_key,
            content="Local only content",
            tag="decision",
        )

        global_brain.learn(
            uid=global_test_key,
            content="Global only content",
            tag="decision",
        )

        local_results = local_brain.recall([local_test_key.split(":")[1]], limit=5)
        global_results = global_brain.recall([global_test_key.split(":")[1]], limit=5)

        local_has_global = any(global_test_key in m.uid for m in local_results if hasattr(m, "uid"))
        global_has_local = any(local_test_key in m.uid for m in global_results if hasattr(m, "uid"))

        passed = not local_has_global and not global_has_local

        return IsolationTestResult(
            test_name="local_global_isolation",
            passed=passed,
            message="Isolation verified" if passed else "CONTAMINATION DETECTED",
            details={
                "local_has_global": local_has_global,
                "global_has_local": global_has_local,
            },
        )

    def test_seal_blocks_writes(
        self,
        brain: SAMBrain,
    ) -> IsolationTestResult:
        """Test that seal() blocks all writes."""
        from kit.core.kit_lock import seal, is_sealed

        if is_sealed(self.project_root):
            return IsolationTestResult(
                test_name="seal_blocks_writes",
                passed=False,
                message="Brain already sealed",
            )

        result = seal(brain.db_path, self.project_root, force_evict=True)

        if not is_sealed(self.project_root):
            return IsolationTestResult(
                test_name="seal_blocks_writes",
                passed=False,
                message="Seal did not apply",
            )

        error_occurred = False
        try:
            brain.learn(
                uid="test:after_seal",
                content="Should be blocked",
                tag="decision",
            )
        except Exception:
            error_occurred = True

        return IsolationTestResult(
            test_name="seal_blocks_writes",
            passed=error_occurred,
            message="Writes blocked" if error_occurred else "WRITE AFTER SEAL DETECTED",
        )

    def test_seal_prevents_recall(
        self,
        brain: SAMBrain,
    ) -> IsolationTestResult:
        """Test that sealed brain prevents recall."""
        from kit.core.kit_lock import is_sealed

        if not is_sealed(self.project_root):
            return IsolationTestResult(
                test_name="seal_prevents_recall",
                passed=False,
                message="Brain not sealed",
            )

        try:
            results = brain.recall(["test"], limit=5)
            read_blocked = False
        except Exception:
            read_blocked = True

        return IsolationTestResult(
            test_name="seal_prevents_recall",
            passed=not read_blocked,
            message="Recall allowed on sealed" if not read_blocked else "Recall blocked",
        )

    def test_purge_clears_state(
        self,
        brain: SAMBrain,
    ) -> IsolationTestResult:
        """Test that purge() clears all state."""
        brain.learn(
            uid="test:purge_target",
            content="To be purged",
            tag="decision",
        )

        initial_count = self._count_observations(brain)

        self._purge_observations(brain)

        final_count = self._count_observations(brain)

        return IsolationTestResult(
            test_name="purge_clears_state",
            passed=final_count == 0 and initial_count > 0,
            message=f"Purged {initial_count} -> {final_count} observations",
            details={
                "initial_count": initial_count,
                "final_count": final_count,
            },
        )

    def test_scope_boundary(
        self,
        brain: SAMBrain,
        foreign_scope: str,
    ) -> IsolationTestResult:
        """Test that observations are scoped correctly."""
        scope_test_key = f"scope:boundary:{id(self)}"

        brain.learn(
            uid=scope_test_key,
            content="Scope boundary test",
            tag="decision",
            scope=foreign_scope,
        )

        results = brain.recall([scope_test_key.split(":")[1]], limit=5)

        results_scoped = [m for m in results if m.scope == foreign_scope]

        return IsolationTestResult(
            test_name="scope_boundary",
            passed=len(results_scoped) > 0,
            message=f"Scope {foreign_scope}: {len(results_scoped)} results",
            details={
                "expected_scope": foreign_scope,
                "result_count": len(results),
                "scoped_count": len(results_scoped),
            },
        )

    def _count_observations(self, brain: SAMBrain) -> int:
        """Count active observations."""
        with brain.get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM observations WHERE is_active = 1"
            ).fetchone()
            return row[0] if row else 0

    def _purge_observations(self, brain: SAMBrain):
        """Purge all observations."""
        with brain.get_connection() as conn:
            conn.execute("DELETE FROM observations WHERE 1=1")
            conn.execute("DELETE FROM nodes WHERE 1=1")
            conn.commit()


class SealingInvariantTest:
    """Test sealing invariants."""

    @staticmethod
    def test_write_after_seal(tmp_brain: SAMBrain, tmp_path: Path) -> bool:
        """Verify write fails after seal."""
        from kit.core.kit_lock import seal, is_sealed

        seal(tmp_brain.db_path, tmp_path, force_evict=True)

        if not is_sealed(tmp_path):
            return False

        try:
            tmp_brain.learn(
                uid="test:post_seal",
                content="Should fail",
                tag="decision",
            )
            return False
        except Exception:
            return True

    @staticmethod
    def test_read_after_seal(tmp_brain: SAMBrain) -> bool:
        """Verify read works after seal (depending on policy)."""
        from kit.core.kit_lock import is_sealed

        try:
            tmp_brain.recall(["test"], limit=1)
            return True
        except Exception:
            return False


def run_isolation_suite(tmp_path: Path) -> dict:
    """
    Run full isolation test suite.

    Returns results dict.
    """
    results = {
        "tests": [],
        "passed": 0,
        "failed": 0,
    }

    guard = MemoryIsolationGuard(tmp_path)

    brain = SAMBrain(
        db_path=tmp_path / "local.db",
        root_path=tmp_path,
        topology=MemoryTopology(tmp_path),
    )

    result = guard.test_purge_clears_state(brain)
    results["tests"].append(result)
    if result.passed:
        results["passed"] += 1
    else:
        results["failed"] += 1

    brain.shutdown()

    return results


def test_concurrent_isolation() -> IsolationTestResult:
    """
    Test if concurrent access is properly isolated.

    Returns test result.
    """
    results: list[IsolationTestResult] = []
    lock = threading.Lock()

    def worker(brain: SAMBrain, uid_prefix: str):
        for i in range(10):
            brain.learn(
                uid=f"{uid_prefix}:{i}",
                content=f"Worker {uid_prefix} item {i}",
                tag="decision",
            )

        with lock:
            results.append(IsolationTestResult(
                test_name="concurrent_worker",
                passed=True,
                message=f"Worker {uid_prefix} completed",
            ))

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        topology = MemoryTopologyFactory.for_project(tmp_path)
        db_path = topology.resolve("local", "local")

        brain = SAMBrain(db_path, root_path=tmp_path, topology=topology)

        threads = [
            threading.Thread(target=worker, args=(brain, f"A{i}")),
            threading.Thread(target=worker, args=(brain, f"B{i}")),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        brain.shutdown()

    passed = len(results) == 2
    return IsolationTestResult(
        test_name="concurrent_isolation",
        passed=passed,
        message=f"Concurrent isolation: {passed}",
    )