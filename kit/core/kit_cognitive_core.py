from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path


class SAMBrainError(Exception):
    """Domain exception for the Cognitive Core."""

    pass


@dataclass(frozen=True)
class Memory:
    """Immutable representation of a retrieved memory fact."""

    id: int
    entity_uid: str
    content: str
    score: float
    distance: int  # 0 for direct match, 1 for neighbor expansion


class SAMBrain:
    """
    Elite Cognitive CRUD API for Structured Agent Memory (.kit).
    Optimized for Python 3.14+ (nogil-ready) and SQL-native ranking.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize SAMBrain with a pathlib Path to the database."""
        if not isinstance(db_path, Path):
            raise SAMBrainError(
                "db_path must be a pathlib.Path instance (code-py-314 doctrine)."
            )

        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a thread-safe connection with deterministic SQL functions."""
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                isolation_level=None,  # Use manual transactions/WAL
            )
            conn.row_factory = sqlite3.Row

            # Register deterministic functions for SQL-level ranking
            conn.create_function("py_log10", 1, math.log10, deterministic=True)
            conn.create_function("py_sqrt", 1, math.sqrt, deterministic=True)

            # Enable WAL mode for high concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")

            return conn
        except sqlite3.Error as e:
            raise SAMBrainError(f"Database connection failed: {e}")

    def _init_db(self) -> None:
        """Initialize schema and indexes."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    kind TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    importance REAL DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    supersedes_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                    FOREIGN KEY (supersedes_id) REFERENCES facts(id) ON DELETE SET NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    source_id INTEGER NOT NULL,
                    target_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    PRIMARY KEY (source_id, target_id, type),
                    FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE CASCADE
                )
            """)
            # Indexes for faster joins and ranking
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_facts_entity ON facts(entity_id) WHERE is_active=1"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_facts_supersedes ON facts(supersedes_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_facts_created ON facts(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rel_source ON relations(source_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rel_target ON relations(target_id)"
            )

    def learn_fact(
        self,
        entity_uid: str,
        kind: str,
        content: str,
        importance: float = 0.5,
        source: str = "agent_session",
        supersedes_id: int | None = None,
    ) -> int:
        """
        Learn a new Fact (Append-only).
        If supersedes_id is provided, the previous fact is linked via lineage.
        """
        try:
            with self._get_connection() as conn:
                # 1. Upsert Entity
                conn.execute(
                    """
                    INSERT INTO entities (uid, kind) VALUES (?, ?)
                    ON CONFLICT(uid) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                """,
                    (entity_uid.lower(), kind),
                )

                # 2. Get Entity ID
                row = conn.execute(
                    "SELECT id FROM entities WHERE uid = ?", (entity_uid.lower(),)
                ).fetchone()
                entity_id = row["id"]

                # 3. Insert New Fact (Always Append)
                cur = conn.execute(
                    """
                    INSERT INTO facts (entity_id, content, source, importance, supersedes_id, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)
                """,
                    (entity_id, content, source, importance, supersedes_id),
                )

                rowid = cur.lastrowid
                assert rowid is not None
                return rowid
        except sqlite3.Error as e:
            raise SAMBrainError(f"Failed to learn fact: {e}")

    def link(
        self, source_uid: str, target_uid: str, rel_type: str, weight: float = 1.0
    ) -> None:
        """Create an Edge between two Nodes."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO relations (source_id, target_id, type, weight)
                    SELECT e1.id, e2.id, ?, ?
                    FROM entities e1, entities e2
                    WHERE e1.uid = ? AND e2.uid = ?
                """,
                    (rel_type, weight, source_uid.lower(), target_uid.lower()),
                )
        except sqlite3.Error as e:
            raise SAMBrainError(f"Failed to link entities: {e}")

    def recall_context(
        self, query_entities: list[str], limit: int = 15
    ) -> list[Memory]:
        """
        Recall ranked context with 1-hop neighbor expansion using SQL-native ranking.
        Only retrieves ACTIVE facts and filters out superseded facts (Leaf nodes only).
        """
        if not query_entities:
            return []

        # Normalize UIDs
        query_entities = [uid.lower() for uid in query_entities]
        placeholders = ",".join(["?"] * len(query_entities))

        # Comprehensive query: Expansion + Ranking + Lineage Filtering (NOT EXISTS)
        sql = f"""
        WITH ExpandedEntities AS (
            -- Direct query entities
            SELECT uid, 0 as distance FROM entities WHERE uid IN ({placeholders})
            UNION
            -- Forward neighbors
            SELECT e2.uid, 1 as distance
            FROM relations r
            JOIN entities e1 ON r.source_id = e1.id
            JOIN entities e2 ON r.target_id = e2.id
            WHERE e1.uid IN ({placeholders})
            UNION
            -- Backward neighbors
            SELECT e1.uid, 1 as distance
            FROM relations r
            JOIN entities e1 ON r.source_id = e1.id
            JOIN entities e2 ON r.target_id = e2.id
            WHERE e2.uid IN ({placeholders})
        )
        SELECT 
            f.id, 
            e.uid as entity_uid, 
            f.content, 
            e_exp.distance,
            (
                f.importance * 
                py_log10(f.access_count + 2) * 
                (1.0 / py_sqrt(MAX(1, julianday('now') - julianday(f.created_at))))
            ) as score
        FROM facts f
        JOIN entities e ON f.entity_id = e.id
        JOIN ExpandedEntities e_exp ON e.uid = e_exp.uid
        WHERE f.is_active = 1 
          AND NOT EXISTS (SELECT 1 FROM facts x WHERE x.supersedes_id = f.id)
        ORDER BY score DESC
        LIMIT ?
        """

        try:
            nodes = []
            params = query_entities + query_entities + query_entities + [limit]

            with self._get_connection() as conn:
                cur = conn.execute(sql, params)
                rows = cur.fetchall()

                if not rows:
                    return []

                # Track IDs for access update
                fact_ids = []
                for row in rows:
                    node = Memory(
                        id=row["id"],
                        entity_uid=row["entity_uid"],
                        content=row["content"],
                        score=row["score"],
                        distance=row["distance"],
                    )
                    nodes.append(node)
                    fact_ids.append(row["id"])

                # Increment access count for recalled facts
                id_placeholders = ",".join(["?"] * len(fact_ids))
                conn.execute(
                    f"UPDATE facts SET access_count = access_count + 1 WHERE id IN ({id_placeholders})",
                    fact_ids,
                )

            return nodes
        except sqlite3.Error as e:
            raise SAMBrainError(f"Recall failed: {e}")

    def export_for_prompt(
        self, query_entities: list[str], limit: int = 10, token_budget: int = 1000
    ) -> str:
        """Render Memory into a highly-compressed format for Agent Prompts."""
        nodes = self.recall_context(query_entities, limit)
        if not nodes:
            return "<sam_memory>\nNo relevant facts found.\n</sam_memory>"

        lines = ["<sam_memory>", "### RELEVANT FACTS:"]
        current_len = sum(len(line) for line in lines)

        for n in nodes:
            line = f"- [{n.entity_uid}]: {n.content}"
            if current_len + len(line) > token_budget:
                break
            lines.append(line)
            current_len += len(line)

        # Include relations if budget allows
        if current_len < token_budget:
            with self._get_connection() as conn:
                placeholders = ",".join(["?"] * len(query_entities))
                rel_sql = f"""
                    SELECT e1.uid as src, r.type, e2.uid as tgt
                    FROM relations r
                    JOIN entities e1 ON r.source_id = e1.id
                    JOIN entities e2 ON r.target_id = e2.id
                    WHERE e1.uid IN ({placeholders}) OR e2.uid IN ({placeholders})
                    LIMIT 5
                """
                rels = conn.execute(rel_sql, query_entities + query_entities).fetchall()
                if rels:
                    lines.append("\n### GRAPH RELATIONS:")
                    for r in rels:
                        lines.append(f"- {r['src']} --({r['type']})--> {r['tgt']}")

        lines.append("</sam_memory>")
        return "\n".join(lines)

    def process_decay(self, decay_factor: float = 0.99) -> None:
        """Maintenance task: Simulate forgetting by scaling down raw importance."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE facts SET importance = importance * ?", (decay_factor,)
                )
        except sqlite3.Error as e:
            raise SAMBrainError(f"Decay process failed: {e}")

    def get_stats(self) -> dict[str, int]:
        """Retrieve cognitive metrics for the brain."""
        try:
            with self._get_connection() as conn:
                entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
                facts = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
                active_facts = conn.execute(
                    "SELECT COUNT(*) FROM facts WHERE is_active = 1"
                ).fetchone()[0]
                relations = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
                lineage = conn.execute(
                    "SELECT COUNT(*) FROM facts WHERE supersedes_id IS NOT NULL"
                ).fetchone()[0]

                return {
                    "entities": entities,
                    "facts": facts,
                    "active_facts": active_facts,
                    "relations": relations,
                    "lineage_links": lineage,
                }
        except sqlite3.Error as e:
            raise SAMBrainError(f"Failed to get stats: {e}")

    def process_compaction(self) -> None:
        """
        Anti-Entropy maintenance: 
        1. Collapse deep lineage chains.
        2. Merge duplicates (WIP - Semantic logic required).
        """
        try:
            with self._get_connection() as conn:
                # Chain collapsing: If A -> B -> C, we can practically jump A -> C
                # for historical audit but keep context clean.
                # Implementation of full collapse logic pending semantic validation.
                pass
        except sqlite3.Error as e:
            raise SAMBrainError(f"Compaction failed: {e}")
