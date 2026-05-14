"""
StateDiff - Snapshot comparison for state verification.

v1.2.5: Computes diffs between brain states and verifies invariants.
"""

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class StateChange:
    """A change in state."""

    table: str
    record_id: Any
    change_type: str  # "added", "removed", "modified"
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)


class StateDiff:
    """Compute diff between two brain snapshots."""

    @staticmethod
    def compute(before_state: dict, after_state: dict) -> dict:
        """
        Compute diff between two states.

        Returns:
        {
            "added": {table: [records],
             "removed": {table: [records],
             "modified": {table: [records]}
        }
        """
        diff = {
            "added": {},
            "removed": {},
            "modified": {},
        }

        all_tables = set(before_state.keys()) | set(after_state.keys())

        for table in all_tables:
            before_rows = {json.dumps(r, sort_keys=True): r for r in before_state.get(table, [])}
            after_rows = {json.dumps(r, sort_keys=True): r for r in after_state.get(table, [])}

            added = set(after_rows.keys()) - set(before_rows.keys())
            removed = set(before_rows.keys()) - set(after_rows.keys())
            common = set(before_rows.keys()) & set(after_rows.keys())

            modified = []
            for key in common:
                if before_rows[key] != after_rows[key]:
                    modified.append(
                        {
                            "before": before_rows[key],
                            "after": after_rows[key],
                        }
                    )

            if added:
                diff["added"][table] = [json.loads(k) for k in added]
            if removed:
                diff["removed"][table] = [json.loads(k) for k in removed]
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
            pass  # New records expected
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

    @staticmethod
    def capture_snapshot(db_path: Path) -> dict:
        """Capture full snapshot of DB."""
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        state = {}

        tables = ["nodes", "observations", "flow_runs", "flow_steps", "metrics"]

        for table in tables:
            try:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                state[table] = [dict(row) for row in rows]
            except sqlite3.OperationalError:
                state[table] = []

        conn.close()
        return state


class FlowStateDiff:
    """Diff focused on flow-related tables."""

    @staticmethod
    def compute(before: dict, after: dict) -> dict:
        """Compute diff for flow tables only."""
        flow_tables = ["flow_runs", "flow_steps", "flow_transactions"]

        return StateDiff.compute(
            {k: v for k, v in before.items() if k in flow_tables},
            {k: v for k, v in after.items() if k in flow_tables},
        )

    @staticmethod
    def has_successful_flow(diff: dict) -> bool:
        """Check if flow completed successfully."""
        for table in ["flow_runs"]:
            if table in diff.get("added", {}):
                for record in diff["added"][table]:
                    if record.get("state") == "success":
                        return True
        return False


class MemoryStateDiff:
    """Diff focused on memory (observations) tables."""

    @staticmethod
    def compute(before: dict, after: dict) -> dict:
        """Compute diff for memory tables only."""
        mem_tables = ["nodes", "observations"]

        return StateDiff.compute(
            {k: v for k, v in before.items() if k in mem_tables},
            {k: v for k, v in after.items() if k in mem_tables},
        )

    @staticmethod
    def get_new_observations(diff: dict) -> list:
        """Get newly added observations."""
        return diff.get("added", {}).get("observations", [])

    @staticmethod
    def get_new_nodes(diff: dict) -> list:
        """Get newly added nodes."""
        return diff.get("added", {}).get("nodes", [])
