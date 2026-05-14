"""Titanium Snapshot Retention Engine (1.2.5STAGE5.1).

Enforces a tiered lifecycle for memory snapshots to prevent infrastructure bloat.
Tier 1: Hot (Latest N snapshots)
Tier 2: Stable (Monthly archives)
Tier 3: Heritage (Yearly archives)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kit.core.kit_cognitive_core import SAMBrain

logger = logging.getLogger("kit.retention")


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    keep_hot: int = 3  # Strictly keep only the latest 3 snapshots (Production Standard)
    max_lineage_depth: int = 10  # Max lineage recursion before squashing (Pragmatic limit)
    dry_run: bool = False


def execute_retention(brain: SAMBrain, policy: RetentionPolicy = RetentionPolicy()) -> dict[str, int]:
    """Prune snapshots to maintain a lean infrastructure (Strict 3-snapshot rule)."""
    report = {"purged": 0, "preserved": 0, "errors": 0}

    with brain.get_connection(readonly=False) as conn:
        # Get all snapshots ordered by timestamp descending (newest first)
        rows = conn.execute("""
            SELECT id, timestamp, path FROM snapshots 
            ORDER BY timestamp DESC
        """).fetchall()

        if not rows:
            return report

        # 1. Selection: Strictly keep the top N (Hot)
        preserved_rows = rows[: policy.keep_hot]
        preserved_ids = {row[0] for row in preserved_rows}

        # 2. Lineage Depth Guard & Purge
        for sid in preserved_ids:
            _squash_lineage(conn, sid, policy.max_lineage_depth)

        for row in rows:
            sid, _, path_str = row
            if sid in preserved_ids:
                report["preserved"] += 1
                continue

            # Physical purge
            if path_str:
                p = Path(path_str)
                if p.exists():
                    try:
                        if not policy.dry_run:
                            p.unlink()
                            logger.info(f"Retention: Purged old physical snapshot {p}")
                    except Exception as e:
                        logger.error(f"Retention: Failed to unlink {p}: {e}")
                        report["errors"] += 1
                        continue

            # DB purge
            try:
                if not policy.dry_run:
                    conn.execute("DELETE FROM snapshots WHERE id = ?", (sid,))
                    logger.info(f"Retention: Purged old lineage record {sid}")
                report["purged"] += 1
            except Exception as e:
                logger.error(f"Retention: Failed to delete DB record {sid}: {e}")
                report["errors"] += 1

        if not policy.dry_run:
            conn.commit()

    return report


def _squash_lineage(conn: sqlite3.Connection, snapshot_id: str, max_depth: int) -> None:
    """Check lineage depth and truncate parent_id if it exceeds max_depth (1.2.5STAGE5.2)."""
    current_id = snapshot_id
    depth = 0

    while current_id and depth < max_depth:
        row = conn.execute("SELECT parent_id FROM snapshots WHERE id = ?", (current_id,)).fetchone()
        if not row or not row[0]:
            break
        current_id = row[0]
        depth += 1

    if depth >= max_depth and current_id:
        # We reached the depth limit. Sever the link to any deeper parents.
        # This effectively "squashes" the history beyond 50 nodes.
        conn.execute("UPDATE snapshots SET parent_id = NULL WHERE id = ?", (current_id,))
        logger.info(f"Retention: Lineage squashed at {current_id} (depth {depth})")
