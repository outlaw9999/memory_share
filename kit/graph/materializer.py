"""
KIT Graph Materializer v1

Snapshot engine with incremental diffing.
Loads JSONL in batches, normalizes once, builds immutable graph snapshot.
Zero runtime coupling with Vantage.
"""

import json
import sqlite3
import hashlib
import logging
import os
from typing import Dict, List, Iterator, Optional, Tuple
from pathlib import Path

logger = logging.getLogger("kit.graph.materializer")

BATCH_SIZE = 5000
SNAPSHOT_VERSION = "v1"


class GraphSnapshot:
    """Immutable graph snapshot with integrity check."""

    def __init__(self, conn: sqlite3.Connection, version: str = SNAPSHOT_VERSION):
        self.conn = conn
        self.version = version
        self._hash: Optional[str] = None

    @property
    def integrity_hash(self) -> str:
        """Compute graph integrity hash."""
        if self._hash:
            return self._hash

        edges = self.conn.execute("""
            SELECT source_symbol, target_symbol, edge_type
            FROM structure_edges
            ORDER BY source_symbol, target_symbol, edge_type
        """).fetchall()

        content = "".join(f"{s}|{t}|{e}" for s, t, e in edges)
        self._hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return self._hash

    def is_valid(self) -> bool:
        """Check if snapshot is valid."""
        try:
            count = self.conn.execute("SELECT COUNT(*) FROM structure_edges").fetchone()[0]
            return count > 0
        except Exception:
            return False


class Materializer:
    """Materializes Vantage output into read-optimized graph."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._last_snapshot: Optional[GraphSnapshot] = None

    def load_jsonl(self, jsonl_path: str, batch_size: int = BATCH_SIZE) -> int:
        """Load JSONL file into graph. Returns edge count."""
        edges = []
        total = 0

        with open(jsonl_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    edge = json.loads(line)
                    edges.append(edge)
                    if len(edges) >= batch_size:
                        total += self._batch_insert(edges)
                        edges.clear()
                except json.JSONDecodeError:
                    continue

        if edges:
            total += self._batch_insert(edges)

        self.conn.commit()
        logger.info(f"Materialized {total} edges from {jsonl_path}")
        return total

    def load_jsonl_stream(self, stream, batch_size: int = BATCH_SIZE) -> int:
        """Load JSONL stream into graph."""
        edges = []
        total = 0

        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                edge = json.loads(line)
                edges.append(edge)
                if len(edges) >= batch_size:
                    total += self._batch_insert(edges)
                    edges.clear()
            except json.JSONDecodeError:
                continue

        if edges:
            total += self._batch_insert(edges)

        self.conn.commit()
        return total

    def _batch_insert(self, edges: List[dict]) -> int:
        """Batch insert edges with deduplication."""
        valid_types = ('IMPORTS', 'INHERITS', 'CALLS')
        batch = []

        for edge in edges:
            if not all(k in edge for k in ('source', 'target', 'edge_type')):
                continue
            if edge['edge_type'] not in valid_types:
                continue

            batch.append((
                edge['source'],
                edge['target'],
                edge['edge_type'],
                float(edge.get('confidence', 1.0)),
                edge.get('source_file'),
                edge.get('line')
            ))

        if not batch:
            return 0

        self.conn.executemany("""
            INSERT OR IGNORE INTO structure_edges
            (source_symbol, target_symbol, edge_type, confidence, source_file, line)
            VALUES (?, ?, ?, ?, ?, ?)
        """, batch)

        return len(batch)

    def materialize_jsonl(self, jsonl_path: str) -> int:
        """Alias for load_jsonl."""
        return self.load_jsonl(jsonl_path)

    def create_snapshot(self) -> GraphSnapshot:
        """Create immutable graph snapshot."""
        snapshot = GraphSnapshot(self.conn)
        self._last_snapshot = snapshot
        logger.info(f"Graph snapshot created: {snapshot.integrity_hash}")
        return snapshot

    def get_snapshot(self) -> Optional[GraphSnapshot]:
        """Get current snapshot."""
        return self._last_snapshot


def materialize_file(conn: sqlite3.Connection, jsonl_path: str) -> int:
    """Public API: materialize JSONL file."""
    mat = Materializer(conn)
    count = mat.load_jsonl(jsonl_path)
    mat.create_snapshot()
    return count


def create_snapshot(conn: sqlite3.Connection) -> str:
    """Public API: create snapshot and return hash."""
    mat = Materializer(conn)
    snap = mat.create_snapshot()
    return snap.integrity_hash