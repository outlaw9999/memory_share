"""
DeterministicSimulator - Mock time/uuid/vantage for reproducible cognitive flow tests.

v1.2.5: Replaces real datetime/uuid/vantage with deterministic mocks
to ensure "same input + same initial brain = same final brain state + same decision tier".
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Generator, Optional
from unittest.mock import patch

from kit.core.kit_cognitive_core import SAMBrain
from kit.core.memory_topology import MemoryTopologyFactory


_SEED_COUNTER = 0
_SEED_TIME = 1700000000.0  # Fixed epoch for reproducibility


def _deterministic_uuid4(seed: int) -> str:
    """Generate deterministic UUID-like string from seed."""
    global _SEED_COUNTER
    _SEED_COUNTER = seed
    return f"00000000-{seed:08x}-0000-0000-000000000000"


def _deterministic_time() -> float:
    """Return deterministic timestamp."""
    return _SEED_TIME


def _deterministic_now() -> datetime:
    """Return deterministic datetime."""
    return datetime.fromtimestamp(_SEED_TIME, tz=timezone.utc)


def _deterministic_strftime(fmt: str) -> str:
    """Return deterministic strftime."""
    return datetime.fromtimestamp(_SEED_TIME, tz=timezone.utc).strftime(fmt)


@dataclass
class SimulatorConfig:
    """Configuration for deterministic simulator."""
    seed: int = 42
    mock_datetime: bool = True
    mock_uuid: bool = True
    mock_vantage: bool = True
    mock_random: bool = True
    vantage_signals: list = field(default_factory=list)


class DeterministickerMock:
    """Mock for Vantage binary - returns predefined signals."""

    def __init__(self, signals: list):
        self.signals = signals
        self.call_count = 0

    def __call__(self, path: Path, *args, **kwargs) -> list:
        self.call_count += 1
        return self.signals

    def __str__(self) -> str:
        return f"DeterministickerMock(calls={self.call_count})"


class FlowSnapshot:
    """Snapshot of brain state at a point in time."""

    def __init__(self, brain: SAMBrain):
        self.brain = brain
        self.db_path = brain.db_path
        self._state: dict = {}
        self._capture()

    def _capture(self):
        """Capture current brain state."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        self._state = {
            "nodes": self._query_table(conn, "nodes"),
            "observations": self._query_table(conn, "observations"),
            "flow_runs": self._query_table(conn, "flow_runs"),
            "flow_steps": self._query_table(conn, "flow_steps"),
            "flow_transactions": self._query_table(conn, "flow_transactions"),
            "metrics": self._query_table(conn, "metrics"),
        }
        conn.close()

    def _query_table(self, conn: sqlite3.Connection, table: str) -> list[dict]:
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            return []

    @property
    def state(self) -> dict:
        return self._state

    def to_dict(self) -> dict:
        """Export snapshot to serializable dict."""
        return {
            "db_path": str(self.db_path),
            "state": self._state,
        }


class DeterministicSimulator:
    """
    Test harness for running cognitive flows deterministically.

    Features:
    - Frozen timestamp for reproducibility
    - Deterministic UUID generation
    - Mock Vantage response
    - Snapshots before/after execution
    """

    _lock = threading.Lock()
    _originals: dict = {}

    def __init__(
        self,
        tmp_path: Path,
        config: Optional[SimulatorConfig] = None,
    ):
        self.tmp_path = tmp_path
        self.config = config or SimulatorConfig()
        self.brain: Optional[SAMBrain] = None
        self._patches: list = []
        self._snapshots: list[FlowSnapshot] = []
        self._start_time: Optional[float] = None

    def setup(self) -> SAMBrain:
        """Initialize brain with deterministic mocks."""
        global _SEED_COUNTER
        _SEED_COUNTER = self.config.seed

        topology = MemoryTopologyFactory.for_project(self.tmp_path)
        db_path = topology.resolve("local", "local")

        self.brain = SAMBrain(db_path, root_path=self.tmp_path, topology=topology)

        self._install_mocks()
        return self.brain

    def _install_mocks(self):
        """Install deterministic mocks."""
        import time
        import uuid as uuid_mod
        import random
        import os

        seed = self.config.seed

        self._patches = []

        if self.config.mock_datetime:
            self._patches.append(patch.object(time, "time", lambda: _SEED_TIME))
            self._patches.append(patch.object(os, "stat", self._mock_stat))
            self._patches.append(patch.object(os, "path", self._mock_path))

    def _mock_path(self, path):
        """Mock path functions."""
        return path

        if self.config.mock_uuid:
            def make_uuid():
                global _SEED_COUNTER
                _SEED_COUNTER += 1
                return _deterministic_uuid4(_SEED_COUNTER)
            self._patches.append(patch.object(uuid_mod, "uuid4", make_uuid))

        if self.config.mock_random:
            rng = random.Random(seed)
            self._patches.append(patch.object(random, "random", rng.random))
            self._patches.append(patch.object(random, "randint", rng.randint))
            self._patches.append(patch.object(random, "choice", rng.choice))

        for p in self._patches:
            p.start()

    def _mock_stat(self, path: Any, *args, **kwargs):
        """Mock stat to return deterministic times."""
        class MockStatResult:
            def __init__(self, mtime):
                self.st_mtime = mtime
                self.st_ctime = mtime
                self.st_atime = mtime
        return MockStatResult(_SEED_TIME)

    def _uninstall_mocks(self):
        """Remove mocks."""
        for p in self._patches:
            p.stop()
        self._patches.clear()

    @contextmanager
    def isolate_vantage(self, signals: list) -> Generator[DeterministickerMock, None, None]:
        """Temporarily mock Vantage response."""
        from kit.core import kit_vantage

        mock_fn = DeterministickerMock(signals)
        original = kit_vantage.invoke_vantage
        kit_vantage.invoke_vantage = mock_fn
        try:
            yield mock_fn
        finally:
            kit_vantage.invoke_vantage = original

    @contextmanager
    def isolate_datetime(self, epoch: float) -> Generator[None, None, None]:
        """Temporarily set deterministic time."""
        global _SEED_TIME
        original = _SEED_TIME
        _SEED_TIME = epoch
        try:
            yield
        finally:
            _SEED_TIME = original

    def snapshot(self, label: str = "") -> FlowSnapshot:
        """Capture brain state snapshot."""
        if not self.brain:
            raise RuntimeError("Simulator not initialized. Call setup() first.")
        snap = FlowSnapshot(self.brain)
        self._snapshots.append(snap)
        if label:
            print(f"[Snapshot] {label}: captured at {_SEED_TIME}")
        return snap

    def diff(self, before: FlowSnapshot, after: FlowSnapshot) -> dict:
        """Compute diff between snapshots."""
        return StateDiff.compute(before, after)

    def run_flow_with_seed(
        self,
        flow_fn: Callable[[SAMBrain], Any],
        seed: int,
    ) -> tuple[FlowSnapshot, FlowSnapshot, Any]:
        """
        Run a cognitive flow with a specific seed.

        Returns (before, after, result).
        """
        global _SEED_COUNTER
        _SEED_COUNTER = seed

        before = self.snapshot(f"before_{seed}")

        result = flow_fn(self.brain)

        after = self.snapshot(f"after_{seed}")

        return before, after, result

    def teardown(self):
        """Clean up simulator."""
        self._uninstall_mocks()
        if self.brain:
            self.brain.shutdown()
            self.brain = None


class StateDiff:
    """Compute and verify state transitions."""

    @staticmethod
    def compute(before: FlowSnapshot, after: FlowSnapshot) -> dict:
        """Compute diff between two snapshots."""
        diff = {
            "added": {},
            "removed": {},
            "modified": {},
        }

        all_tables = set(before.state.keys()) | set(after.state.keys())

        for table in all_tables:
            before_rows = {json.dumps(r, sort_keys=True): r for r in before.state.get(table, [])}
            after_rows = {json.dumps(r, sort_keys=True): r for r in after.state.get(table, [])}

            added = set(after_rows.keys()) - set(before_rows.keys())
            removed = set(before_rows.keys()) - set(after_rows.keys())
            common = set(before_rows.keys()) & set(after_rows.keys())

            modified = []
            for key in common:
                if before_rows[key] != after_rows[key]:
                    modified.append({
                        "before": before_rows[key],
                        "after": after_rows[key],
                    })

            if added:
                diff["added"][table] = [after_rows[k] for k in added]
            if removed:
                diff["removed"][table] = [before_rows[k] for k in removed]
            if modified:
                diff["modified"][table] = modified

        return diff

    @staticmethod
    def verify_invariant(
        diff: dict,
        expected_tables: list[str],
        allow_inserts: bool = True,
    ) -> tuple[bool, str]:
        """
        Verify state changes match expected pattern.

        Returns (is_valid, message).
        """
        for table in expected_tables:
            if table in diff.get("removed", {}):
                if diff["removed"][table]:
                    return False, f"Unexpected removal from {table}"

        if allow_inserts:
            for table in expected_tables:
                if table in diff.get("added", {}):
                    pass  # Expected new records
        else:
            for table in expected_tables:
                if table in diff.get("added", {}):
                    return False, f"Unexpected new records in {table}"

        return True, "Invariant preserved"

    @staticmethod
    def summarize(diff: dict) -> str:
        """Human-readable diff summary."""
        lines = []

        for table, records in diff.get("added", {}).items():
            lines.append(f"  +{table}: {len(records)} added")

        for table, records in diff.get("removed", {}).items():
            lines.append(f"  -{table}: {len(records)} removed")

        modified = sum(len(v) for v in diff.get("modified", {}).values())
        if modified:
            lines.append(f"  ~modified: {modified} records")

        if not lines:
            return "  (no changes)"

        return "\n".join(lines)