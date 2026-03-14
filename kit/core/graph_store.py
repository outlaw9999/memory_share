import os
import sqlite3
import time
import re
import hashlib
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union, Tuple

from .models import CallSite, Symbol


SYMBOL_FTS_USING = """
fts5(
    name,
    content='symbols',
    content_rowid='rowid',
    tokenize='unicode61',
    prefix='2 3'
)
"""

DEFAULT_DIR = ".memory_share_kit"


def get_kit_home() -> Path:
    """
    Resolve the runtime directory for .kit storage.

    Priority order:
    1. KIT_HOME environment variable
    2. Project local directory (.memory_share_kit)
    """
    env_home = os.environ.get("KIT_HOME")

    if env_home:
        home = Path(env_home).expanduser().resolve()
    else:
        home = Path.cwd() / DEFAULT_DIR

    home.mkdir(parents=True, exist_ok=True)
    return home


def get_db_path() -> Path:
    """
    Return path to the atlas database.
    """
    return get_kit_home() / "atlas_v1.db"


class GraphStore:
    def __init__(
        self, db_path: Optional[Union[str, Path]] = None
    ) -> None:
        if db_path is None:
            self.db_path = get_db_path()
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._symbol_fts_enabled = False
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()  # Reentrant lock for thread safety

        # Phase 12 Refinements: Better Concurrency
        self.conn.execute("PRAGMA busy_timeout=5000;")

        # Enable WAL mode for concurrent reads (agents querying in parallel)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")

        # Allow readers to proceed without blocking on writes
        self.conn.execute("PRAGMA query_only=False;")

        # Use in-memory temp tables for performance
        self.conn.execute("PRAGMA temp_store=MEMORY;")

        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS symbols (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fqn TEXT UNIQUE NOT NULL,
                    kind TEXT,
                    file_path TEXT,
                    importance_score REAL DEFAULT 0.0
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS symbol_aliases (
                    alias TEXT NOT NULL,
                    normalized_alias TEXT NOT NULL,
                    symbol_id INTEGER NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    FOREIGN KEY(symbol_id) REFERENCES symbols(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS edges (
                    source_id INTEGER NOT NULL,
                    target_alias TEXT NOT NULL,
                    layer INTEGER NOT NULL,
                    type TEXT,
                    FOREIGN KEY(source_id) REFERENCES symbols(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS file_registry (
                    file_path TEXT PRIMARY KEY,
                    last_hash TEXT NOT NULL,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS assertions (
                    node_id INTEGER PRIMARY KEY,
                    doc_id INTEGER,
                    raw_text TEXT,
                    confidence REAL DEFAULT 1.0,
                    FOREIGN KEY(node_id) REFERENCES symbols(id),
                    FOREIGN KEY(doc_id) REFERENCES symbols(id)
                )
                """
            )
            # Machine Interface: Metadata and Schema Versioning
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            # Initialize schema_version if not exists
            cur.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1')"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_alias_lookup ON symbol_aliases(normalized_alias)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_symbol_file ON symbols(file_path)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_symbols_fqn ON symbols(fqn)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind)")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_source_layer ON edges(source_id, layer)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_target_alias ON edges(target_alias)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(type)")

            self._init_symbol_search(cur)
            self.conn.commit()

    def _init_symbol_search(self, cur: sqlite3.Cursor) -> None:
        try:
            row = cur.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'symbol_fts'"
            ).fetchone()
            if self._symbol_fts_requires_migration(row[0] if row is not None else None):
                self._recreate_symbol_search(cur)
            else:
                cur.execute(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS symbol_fts USING {SYMBOL_FTS_USING}"
                )

            self._ensure_symbol_search_triggers(cur)

            symbol_count = cur.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
            fts_count = cur.execute("SELECT COUNT(*) FROM symbol_fts").fetchone()[0]
            if symbol_count != fts_count:
                cur.execute("INSERT INTO symbol_fts(symbol_fts) VALUES ('rebuild')")

            self._symbol_fts_enabled = True
        except sqlite3.OperationalError:
            self._symbol_fts_enabled = False

    def _symbol_fts_requires_migration(self, sql: Optional[str]) -> bool:
        if sql is None:
            return False

        normalized = " ".join(sql.lower().split())
        return (
            "tokenize='unicode61'" not in normalized or "prefix='2 3'" not in normalized
        )

    def _recreate_symbol_search(self, cur: sqlite3.Cursor) -> None:
        cur.execute("DROP TRIGGER IF EXISTS symbols_ai")
        cur.execute("DROP TRIGGER IF EXISTS symbols_ad")
        cur.execute("DROP TRIGGER IF EXISTS symbols_au")
        cur.execute("DROP TABLE IF EXISTS symbol_fts")
        cur.execute(f"CREATE VIRTUAL TABLE symbol_fts USING {SYMBOL_FTS_USING}")

    def _ensure_symbol_search_triggers(self, cur: sqlite3.Cursor) -> None:
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
                INSERT INTO symbol_fts(rowid, name) VALUES (new.id, new.fqn);
            END
            """
        )
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
                INSERT INTO symbol_fts(symbol_fts, rowid, name) VALUES ('delete', old.id, old.fqn);
            END
            """
        )
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE OF fqn ON symbols BEGIN
                INSERT INTO symbol_fts(symbol_fts, rowid, name) VALUES ('delete', old.id, old.fqn);
                INSERT INTO symbol_fts(rowid, name) VALUES (new.id, new.fqn);
            END
            """
        )

    # ---------------- SYMBOLS ----------------

    def add_symbol(
        self, fqn: str, kind: Optional[str] = None, file_path: Optional[str] = None
    ) -> int:
        with self._lock:
            cur = self.conn.cursor()

            cur.execute(
                """
        INSERT OR IGNORE INTO symbols(fqn, kind, file_path)
        VALUES (?, ?, ?)
        """,
                (fqn, kind, str(file_path) if file_path else None),
            )

            self.conn.commit()

            cur.execute("SELECT id FROM symbols WHERE fqn=?", (fqn,))
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(f"Failed to insert symbol: {fqn}")
            symbol_id: int = row[0]
            return symbol_id

    def delete_file_metadata(self, file_path: Path) -> None:
        """Xóa toàn bộ symbol, alias và edge liên quan đến một file để chuẩn bị re-index."""
        with self._lock:
            cur = self.conn.cursor()

            # Lấy danh sách symbol IDs của file
            cur.execute("SELECT id FROM symbols WHERE file_path=?", (str(file_path),))
            symbol_ids = [row[0] for row in cur.fetchall()]

            if symbol_ids:
                placeholders = ",".join(["?"] * len(symbol_ids))
                # Xóa aliases
                cur.execute(
                    f"DELETE FROM symbol_aliases WHERE symbol_id IN ({placeholders})",
                    symbol_ids,
                )
                # Xóa edges (source_id)
                cur.execute(
                    f"DELETE FROM edges WHERE source_id IN ({placeholders})", symbol_ids
                )
                # Xóa chính symbols
                cur.execute(
                    f"DELETE FROM symbols WHERE id IN ({placeholders})", symbol_ids
                )

            self.conn.commit()

    def update_file_registry(self, file_path: Path, file_hash: str) -> None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
            INSERT OR REPLACE INTO file_registry(file_path, last_hash, indexed_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
                (str(file_path), file_hash),
            )
            self.conn.commit()

    def get_registered_hash(self, file_path: Path) -> Optional[str]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT last_hash FROM file_registry WHERE file_path=?",
                (str(file_path),),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def find_symbol_by_alias(self, alias: str) -> Optional[int]:
        """Resolve an alias to a symbol ID."""
        with self._lock:
            return self.resolve_alias(alias)

    def create_document_node(self, path: Path) -> int:
        """Create a node for a documentation file."""
        return self.add_symbol(str(path), kind="document", file_path=str(path))

    def create_assertion(self, doc_id: int, text: str, confidence: float = 1.0) -> int:
        """Create an assertion node and link it to its document."""
        # Use a hash + timestamp for a unique FQN
        h = hashlib.md5(text.encode()).hexdigest()[:8]
        fqn = f"assertion:{h}:{time.time()}"
        node_id = self.add_symbol(fqn, kind="assertion")

        cur = self.conn.cursor()
        cur.execute(
            """
        INSERT INTO assertions(node_id, doc_id, raw_text, confidence)
        VALUES (?, ?, ?, ?)
        """,
            (node_id, doc_id, text, confidence),
        )

        # Link Doc -> Assertion (Layer 2)
        # Note: add_edge_by_alias expects an alias for target.
        # For internal nodes, we use the FQN as the alias.
        self.add_alias(fqn, node_id)
        self.add_edge_by_alias(doc_id, fqn, layer=2)

        self.conn.commit()
        return node_id

    def update_importance_scores(self, scores: dict[int, float]) -> None:
        cur = self.conn.cursor()
        data = [(score, symbol_id) for symbol_id, score in scores.items()]
        cur.executemany("UPDATE symbols SET importance_score=? WHERE id=?", data)
        self.conn.commit()

    # ---------------- ALIASES ----------------

    def add_alias(self, alias: str, symbol_id: int, confidence: float = 1.0) -> None:
        normalized = alias.lower()

        cur = self.conn.cursor()

        cur.execute(
            """
        INSERT INTO symbol_aliases(alias, normalized_alias, symbol_id, confidence)
        VALUES (?, ?, ?, ?)
        """,
            (alias, normalized, symbol_id, confidence),
        )

        self.conn.commit()

    # ---------------- EDGES ----------------

    def add_edge_by_alias(
        self, source_id: int, target_alias: str, layer: int = 1, type: str = "calls"
    ) -> None:
        """Add an edge (dependency/relation) to the graph."""
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO edges (source_id, target_alias, layer, type) VALUES (?, ?, ?, ?)",
            (source_id, target_alias.lower(), layer, type),
        )
        self.conn.commit()

    def add_edge(self, *args: Any, **kwargs: Any) -> None:
        """Legacy compatibility."""
        return self.add_edge_by_alias(*args, **kwargs)

    # ---------------- RESOLUTION ----------------

    def resolve_alias(self, alias: str) -> Optional[int]:
        with self._lock:
            cur = self.conn.cursor()

            cur.execute(
                """
        SELECT symbol_id
        FROM symbol_aliases
        WHERE normalized_alias=?
        ORDER BY confidence DESC
        LIMIT 1
        """,
                (alias.lower(),),
            )

            row = cur.fetchone()

            return row[0] if row else None

    def _apply_once(
        self,
        file_path: str,
        symbol_rows: list[tuple[str, str, str, int]],
        call_rows: list[tuple[str, str, str, int]],
        txn_id: str,
        ts: float,
    ) -> bool:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("BEGIN")
            try:
                row = cur.execute(
                    "SELECT 1 FROM applied_txns WHERE txn_id = ?", (txn_id,)
                ).fetchone()
                if row is not None:
                    self.conn.rollback()
                    return False

                cur.execute("DELETE FROM symbols WHERE file = ?", (file_path,))
                cur.execute("DELETE FROM calls WHERE file = ?", (file_path,))
                cur.executemany(
                    "INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
                    symbol_rows,
                )
                cur.executemany(
                    "INSERT OR IGNORE INTO calls (caller, callee, file, line) VALUES (?, ?, ?, ?)",
                    call_rows,
                )
                cur.execute(
                    "INSERT INTO applied_txns (txn_id, file, ts) VALUES (?, ?, ?)",
                    (txn_id, file_path, ts),
                )
                self.conn.commit()
                return True
            except sqlite3.Error:
                self.conn.rollback()
                raise

    def list_applied_txns(self) -> list[str]:
        with self._lock:
            cur = self.conn.cursor()
            rows = cur.execute(
                "SELECT txn_id FROM applied_txns ORDER BY ts, txn_id"
            ).fetchall()
            return [txn_id for (txn_id,) in rows]

    def cleanup_applied_txns(
        self, retention_seconds: float, *, now: Optional[float] = None
    ) -> int:
        with self._lock:
            cutoff = (time.time() if now is None else now) - retention_seconds
            cur = self.conn.cursor()
            cur.execute("DELETE FROM applied_txns WHERE ts < ?", (cutoff,))
            self.conn.commit()
            return cur.rowcount

    def list_symbols(self, path: Union[Path, None] = None) -> List[Symbol]:
        with self._lock:
            cur = self.conn.cursor()
            if path is None:
                rows = cur.execute(
                    "SELECT name, kind, file, line FROM symbols ORDER BY file, line"
                ).fetchall()
            else:
                rows = cur.execute(
                    "SELECT name, kind, file, line FROM symbols WHERE file = ? ORDER BY line",
                    (str(path),),
                ).fetchall()
            return [Symbol(name, kind, file, line) for name, kind, file, line in rows]

    def search_symbols(
        self, query: str, limit: int = 10, fuzzy: bool = True
    ) -> List[Symbol]:
        with self._lock:
            cur = self.conn.cursor()
            normalized_query = query.strip()
            if not normalized_query:
                return []

            rows = []
            if self._symbol_fts_enabled:
                fts_query = self._build_fts_query(normalized_query)
                if fts_query is not None:
                    rows = cur.execute(
                        """
                        SELECT s.name, s.kind, s.file, s.line
                        FROM symbol_fts
                        JOIN symbols AS s ON s.rowid = symbol_fts.rowid
                        WHERE symbol_fts MATCH ?
                        ORDER BY s.name
                        LIMIT ?
                        """,
                        (fts_query, limit),
                    ).fetchall()

            if not rows and fuzzy:
                rows = cur.execute(
                    "SELECT name, kind, file, line FROM symbols WHERE name LIKE ? ORDER BY name LIMIT ?",
                    (f"%{normalized_query}%", limit),
                ).fetchall()
            elif not rows:
                rows = cur.execute(
                    "SELECT name, kind, file, line FROM symbols WHERE name LIKE ? ORDER BY name LIMIT ?",
                    (f"{normalized_query}%", limit),
                ).fetchall()

            return [Symbol(name, kind, file, line) for name, kind, file, line in rows]

    def _build_fts_query(self, query: str) -> Optional[str]:
        tokens = re.findall(r"[0-9A-Za-z_]+", query)
        if not tokens:
            return None
        return " ".join(f"{token}*" for token in tokens)

    def search_related_symbols(
        self,
        query: str,
        *,
        exclude_name: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        with self._lock:
            normalized_query = query.strip()
            if not normalized_query or not self._symbol_fts_enabled:
                return []

            fts_query = self._build_fts_query(normalized_query)
            if fts_query is None:
                return []

            candidate_limit = max(limit * 5, 50)
            sql = """
            WITH candidates AS (
                SELECT
                    s.rowid,
                    s.name,
                    s.kind,
                    s.file,
                    s.line,
                    bm25(symbol_fts) AS fts_rank
                FROM symbol_fts
                JOIN symbols AS s ON s.rowid = symbol_fts.rowid
                WHERE symbol_fts MATCH ?
            """
            params: list[object] = [fts_query]
            if exclude_name:
                sql += " AND s.name != ?"
                params.append(exclude_name)

            sql += """
                ORDER BY
                    bm25(symbol_fts) ASC,
                    length(s.name) ASC,
                    s.name ASC,
                    s.file ASC,
                    s.line ASC
                LIMIT ?
            ),
            ranked_candidates AS (
                SELECT
                    rowid,
                    name,
                    kind,
                    file,
                    line,
                    fts_rank,
                    ROW_NUMBER() OVER (PARTITION BY name ORDER BY file) AS name_rank
                FROM candidates
            ),
            degree AS (
                SELECT rowid, SUM(cnt) AS deg
                FROM (
                    SELECT rc.rowid, COUNT(*) AS cnt
                    FROM ranked_candidates AS rc
                    JOIN calls ON calls.caller = rc.name
                    WHERE rc.name_rank = 1
                    GROUP BY rc.rowid
                    UNION ALL
                    SELECT rc.rowid, COUNT(*) AS cnt
                    FROM ranked_candidates AS rc
                    JOIN calls ON calls.callee = rc.name
                    WHERE rc.name_rank = 1
                    GROUP BY rc.rowid
                )
                GROUP BY rowid
            )
            SELECT
                rc.name,
                rc.kind,
                rc.file,
                rc.line,
                rc.fts_rank,
                COALESCE(d.deg, 0) AS degree
            FROM ranked_candidates AS rc
            LEFT JOIN degree AS d ON d.rowid = rc.rowid
            """
            params.append(candidate_limit)

            sql += """
            ORDER BY
                rc.fts_rank ASC,
                COALESCE(d.deg, 0) DESC,
                length(rc.name) ASC,
                rc.name ASC,
                rc.file ASC,
                rc.line ASC
            LIMIT ?
            """
            params.append(limit)

            cur = self.conn.cursor()
            rows = cur.execute(sql, params).fetchall()
            return [
                {
                    "name": name,
                    "kind": kind,
                    "file": file,
                    "line": line,
                    "fts_rank": fts_rank,
                    "degree": degree,
                }
                for name, kind, file, line, fts_rank, degree in rows
            ]

    def find_callers(self, callee_alias: str, limit: int = 50) -> List[CallSite]:
        cur = self.conn.cursor()
        # In V1, edges link source_id to target_alias.
        # We try to match the full FQN first, then fall back to the short name.
        short_name = callee_alias.split(".")[-1]

        rows = cur.execute(
            """
            SELECT s.fqn as caller, e.target_alias as callee, s.file_path, '?' as line
            FROM edges e
            JOIN symbols s ON e.source_id = s.id
            WHERE (e.target_alias = ? OR e.target_alias = ?) AND e.layer IN (0, 1)
            LIMIT ?
            """,
            (callee_alias.lower(), short_name.lower(), limit),
        ).fetchall()
        return [
            CallSite(caller, callee, file, line) for caller, callee, file, line in rows
        ]

    def find_callees(self, source_id: int, limit: int = 50) -> List[CallSite]:
        with self._lock:
            cur = self.conn.cursor()
            rows = cur.execute(
                """
                SELECT s.fqn as caller, e.target_alias as callee, s.file_path, '?' as line
                FROM edges e
                JOIN symbols s ON e.source_id = s.id
                WHERE e.source_id = ? AND e.layer = 1
                LIMIT ?
                """,
                (source_id, limit),
            ).fetchall()
            return [
                CallSite(caller, callee, file, line)
                for caller, callee, file, line in rows
            ]

    def trace_impact(
        self, symbol_alias: str, max_depth: int = 5, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Reverse call graph traversal: Find all symbols that depend on this symbol.
        """
        with self._lock:
            cur = self.conn.cursor()

            sql = """
            WITH RECURSIVE reverse_impact(source_id, depth) AS (
                -- Base case: Find direct callers of the target symbol alias
                SELECT DISTINCT source_id, 1
                FROM edges
                WHERE target_alias = ? AND layer = 1
                
                UNION
                
                -- Recursive case: Find callers of callers
                SELECT DISTINCT e.source_id, ri.depth + 1
                FROM edges e
                JOIN symbols s ON e.target_alias = s.fqn -- This is slow but necessary given current schema
                JOIN reverse_impact ri ON s.id = ri.source_id
                WHERE ri.depth < ? AND e.layer = 1
            )
            SELECT DISTINCT s.fqn, ri.depth, s.file_path
            FROM reverse_impact ri
            JOIN symbols s ON ri.source_id = s.id
            ORDER BY ri.depth ASC, s.fqn ASC
            LIMIT ?
            """

            try:
                rows = cur.execute(
                    sql, (symbol_alias.lower(), max_depth, limit)
                ).fetchall()

                result = []
                for name, depth, path in rows:
                    result.append(
                        {
                            "name": name,
                            "depth": depth,
                            "path": path,
                            "line": "?",
                        }
                    )

                return result
            except sqlite3.Error as e:
                print(f"Error in trace_impact: {e}")
                return []

    def update_file(
        self,
        file_path: Path,
        symbols: list[Any],
        calls: list[Any],
        txn_id: Optional[str] = None,
        ts: Optional[float] = None,
    ) -> bool:
        """Legacy method - not implemented. Use IncrementalUpdater instead."""
        raise NotImplementedError("Use IncrementalUpdater.update_file_delta instead")
