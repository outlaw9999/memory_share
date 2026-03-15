import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kit.core import schema_factory
from kit.core.schema_factory import enable_wal, init_db


class SAMBrainError(Exception):
    """Domain exception for the Cognitive Core."""
    pass


@dataclass(frozen=True, slots=True)
class Memory:
    """Immutable representation of a retrieved memory fact (v3.14 compliant)."""
    id: int
    node_uid: str
    content: str
    score: float
    brain_source: str


class SAMBrain:
    """
    Elite Cognitive Quad-Store AI Kernel (.kit).
    Hybrid Brain support (Local + Global) with Temporal Graph logic.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.global_db_path: Path | None = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                isolation_level=None,
            )
            conn.row_factory = sqlite3.Row
            enable_wal(conn)
            return conn
        except sqlite3.Error as e:
            raise SAMBrainError(f"Database connection failed: {e}")

    def attach_global(self, global_db_path: Path) -> None:
        """Attach the global brain for unified queries."""
        self.global_db_path = global_db_path
        # Initialize the global DB schema if it doesn't exist
        with sqlite3.connect(str(global_db_path)) as gconn:
            init_db(gconn)

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            init_db(conn)

    def learn(
        self,
        uid: str,
        content: str,
        kind: str = "observation",
        importance: float = 1.0,
        layer: str = "episodic",
        metadata: dict[str, Any] | None = None,
        to_global: bool = False,
        supersede_id: int | None = None,
    ) -> int:
        """Learn a new observation at a specific node."""
        target_db = self.global_db_path if (to_global and self.global_db_path) else self.db_path
        
        try:
            with sqlite3.connect(str(target_db)) as conn:
                conn.row_factory = sqlite3.Row
                
                # 0. Handle Supersede
                if supersede_id:
                    conn.execute(
                        "UPDATE observations SET superseded_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (supersede_id,)
                    )

                # 1. Upsert Node
                conn.execute(
                    "INSERT INTO nodes (uid, kind) VALUES (?, ?) ON CONFLICT(uid) DO UPDATE SET uid=uid",
                    (uid.lower(), kind)
                )
                node_row = conn.execute("SELECT id FROM nodes WHERE uid = ?", (uid.lower(),)).fetchone()
                node_id = node_row["id"]

                # 2. Insert Observation
                meta_json = json.dumps(metadata or {})
                cur = conn.execute(
                    """
                    INSERT INTO observations (node_id, content, layer, importance, metadata)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (node_id, content, layer, importance, meta_json)
                )
                return cur.lastrowid
        except sqlite3.Error as e:
            raise SAMBrainError(f"Failed to learn observation: {e}")

    def link(
        self,
        src_uid: str,
        dst_uid: str,
        rel: str,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Create a directed edge between two nodes."""
        try:
            with self._get_connection() as conn:
                src_row = conn.execute("SELECT id FROM nodes WHERE uid = ?", (src_uid.lower(),)).fetchone()
                dst_row = conn.execute("SELECT id FROM nodes WHERE uid = ?", (dst_uid.lower(),)).fetchone()
                
                if not src_row or not dst_row:
                    raise SAMBrainError(f"Node not found: {src_uid if not src_row else dst_uid}")

                meta_json = json.dumps(metadata or {"weight": weight})
                conn.execute(
                    "INSERT INTO edges (subject_id, predicate, object_id, metadata) VALUES (?, ?, ?, ?)",
                    (src_row["id"], rel, dst_row["id"], meta_json)
                )
        except sqlite3.Error as e:
            raise SAMBrainError(f"Failed to link nodes: {e}") from e

    def search(self, query: str, limit: int = 15, at_timestamp: str | None = None) -> list[Memory]:
        """Hybrid FTS Search across both brains."""
        ts = at_timestamp or "now"
        
        results = []

        def run_query(conn, prefix="", priority=1.0, source="project"):
            p = f"{prefix}." if prefix else ""
            sql = f"""
            SELECT o.*, n.uid as node_uid,
            (
                o.importance
                * ((o.access_count + 1) / (o.access_count + 5.0))
                * EXP(-0.0231 * (JULIANDAY(?) - JULIANDAY(o.created_at)))
                * {priority}
                * CASE o.layer
                    WHEN 'working' THEN 3.0
                    WHEN 'episodic' THEN 2.0
                    WHEN 'semantic' THEN 1.5
                    ELSE 1.0
                END
            ) AS score
            FROM {p}observations o
            JOIN {p}nodes n ON o.node_id = n.id
            WHERE o.id IN (SELECT rowid FROM {p}observations_fts WHERE {p}observations_fts MATCH ?)
              AND julianday(o.created_at) <= julianday(?)
              AND ({p}observations.superseded_at IS NULL OR julianday({p}observations.superseded_at) > julianday(?))
            ORDER BY score DESC
            LIMIT {limit}
            """
            cur = conn.execute(sql, (ts, query, ts, ts))
            for row in cur.fetchall():
                results.append(Memory(
                    id=row["id"],
                    node_uid=row["node_uid"],
                    content=row["content"],
                    score=row["score"],
                    brain_source=source
                ))

        # 1. Project Brain
        with self._get_connection() as conn:
            run_query(conn, priority=1.5, source="project")

        # 2. Global Brain
        if self.global_db_path:
            with sqlite3.connect(str(self.global_db_path)) as gconn:
                gconn.row_factory = sqlite3.Row
                run_query(gconn, priority=1.0, source="global")

        # Sort combined results
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def recall(self, entities: list[str], limit: int = 15, at_timestamp: str | None = None) -> list[Memory]:
        """Recall context for nodes by UID across both brains."""
        if not entities:
            return []
        
        ts = at_timestamp or "now"
        results = []
        uids = [e.lower() for e in entities]

        # Internal helper for querying a single brain
        def _recall_from(conn, prefix="", priority=1.0, source="project"):
            p = f"{prefix}." if prefix else ""
            placeholders = ",".join(["?"] * len(uids))
            sql = f"""
            SELECT o.*, n.uid as node_uid,
            (
                o.importance
                * ((o.access_count + 1) / (o.access_count + 5.0))
                * EXP(-0.0231 * (JULIANDAY(?) - JULIANDAY(o.created_at)))
                * {priority}
                * CASE o.layer
                    WHEN 'working' THEN 3.0
                    WHEN 'episodic' THEN 2.0
                    WHEN 'semantic' THEN 1.5
                    ELSE 1.0
                END
            ) AS score
            FROM {p}observations o
            JOIN {p}nodes n ON o.node_id = n.id
            WHERE n.uid IN ({placeholders})
              AND julianday(o.created_at) <= julianday(?)
              AND (o.superseded_at IS NULL OR julianday(o.superseded_at) > julianday(?))
            ORDER BY score DESC
            LIMIT {limit}
            """
            params = [ts] + uids + [ts, ts]
            cur = conn.execute(sql, params)
            for row in cur.fetchall():
                results.append(Memory(
                    id=row["id"],
                    node_uid=row["node_uid"],
                    content=row["content"],
                    score=row["score"],
                    brain_source=source
                ))

        with self._get_connection() as conn:
            _recall_from(conn, priority=1.5, source="project")
            if self.global_db_path:
                with sqlite3.connect(str(self.global_db_path)) as gconn:
                    gconn.row_factory = sqlite3.Row
                    _recall_from(gconn, priority=1.0, source="global")

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def get_stats(self) -> dict[str, Any]:
        """Retrieve dual-brain metrics."""
        stats = {"project": {}, "global": {}}
        
        def get_db_stats(conn, prefix=""):
            p = f"{prefix}." if prefix else ""
            return {
                "nodes": conn.execute(f"SELECT COUNT(*) FROM {p}nodes").fetchone()[0],
                "edges": conn.execute(f"SELECT COUNT(*) FROM {p}edges").fetchone()[0],
                "observations": conn.execute(f"SELECT COUNT(*) FROM {p}observations").fetchone()[0],
            }

        with self._get_connection() as conn:
            stats["project"] = get_db_stats(conn)
            if self.global_db_path:
                conn.execute(f"ATTACH DATABASE '{self.global_db_path}' AS g")
                stats["global"] = get_db_stats(conn, "g")
        return stats

    def process_gc(self) -> None:
        """Memory lifecycle maintenance (WIP - Phase 3 focus)."""
        pass

    def export_for_prompt(self, entities: list[str], limit: int = 10, budget: int = 1000) -> str:
        """Compact memory export for LLM prompts."""
        memories = self.recall(entities, limit)
        if not memories:
            return "<kit_memory>\nNo relevant memories found.\n</kit_memory>"
            
        output = ["<kit_memory>"]
        for m in memories:
            output.append(f"[{m.brain_source}:{m.node_uid}] {m.content}")
        output.append("</kit_memory>")
        return "\n".join(output)
