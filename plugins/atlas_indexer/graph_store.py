import sqlite3
import time
import re
from pathlib import Path
from typing import Iterable, List, Optional, Union

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


class GraphStore:
    def __init__(self, db_path: Union[str, Path] = ".antigravity/atlas/atlas.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._symbol_fts_enabled = False
        self.conn = sqlite3.connect(self.db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS symbols (
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS applied_txns (
                txn_id TEXT PRIMARY KEY,
                file TEXT NOT NULL,
                ts REAL NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS calls (
                caller TEXT NOT NULL,
                callee TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL
            )
            """
        )
        self._init_symbol_search(cur)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)")
        cur.execute("DROP INDEX IF EXISTS idx_calls_callee")
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_calls_callee_cover
            ON calls(callee, file, line, caller)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_calls_caller_cover
            ON calls(caller, file, line, callee)
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_calls_file ON calls(file)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_applied_txns_ts ON applied_txns(ts)")
        self.conn.commit()

    def _init_symbol_search(self, cur: sqlite3.Cursor) -> None:
        try:
            row = cur.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'symbol_fts'"
            ).fetchone()
            if self._symbol_fts_requires_migration(row[0] if row is not None else None):
                self._recreate_symbol_search(cur)
            else:
                cur.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS symbol_fts USING {SYMBOL_FTS_USING}")

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
        return "tokenize='unicode61'" not in normalized or "prefix='2 3'" not in normalized

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
                INSERT INTO symbol_fts(rowid, name) VALUES (new.rowid, new.name);
            END
            """
        )
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
                INSERT INTO symbol_fts(symbol_fts, rowid, name) VALUES ('delete', old.rowid, old.name);
            END
            """
        )
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE OF name ON symbols BEGIN
                INSERT INTO symbol_fts(symbol_fts, rowid, name) VALUES ('delete', old.rowid, old.name);
                INSERT INTO symbol_fts(rowid, name) VALUES (new.rowid, new.name);
            END
            """
        )

    def update_file(
        self,
        path: Union[str, Path],
        symbols: Iterable[Symbol],
        calls: Iterable[CallSite] = (),
        *,
        txn_id: Optional[str] = None,
        ts: Optional[float] = None,
    ) -> bool:
        file_path = str(Path(path))
        symbol_rows = [(symbol.name, symbol.kind, symbol.file, symbol.line) for symbol in symbols]
        call_rows = [(call.caller, call.callee, call.file, call.line) for call in calls]
        if txn_id is not None:
            return self._apply_once(file_path, symbol_rows, call_rows, txn_id, ts or 0.0)

        cur = self.conn.cursor()
        cur.execute("DELETE FROM symbols WHERE file = ?", (file_path,))
        cur.execute("DELETE FROM calls WHERE file = ?", (file_path,))
        cur.executemany(
            "INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
            symbol_rows,
        )
        cur.executemany(
            "INSERT INTO calls (caller, callee, file, line) VALUES (?, ?, ?, ?)",
            call_rows,
        )
        self.conn.commit()
        return True

    def _apply_once(
        self,
        file_path: str,
        symbol_rows: list[tuple[str, str, str, int]],
        call_rows: list[tuple[str, str, str, int]],
        txn_id: str,
        ts: float,
    ) -> bool:
        cur = self.conn.cursor()
        cur.execute("BEGIN")
        try:
            row = cur.execute("SELECT 1 FROM applied_txns WHERE txn_id = ?", (txn_id,)).fetchone()
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
                "INSERT INTO calls (caller, callee, file, line) VALUES (?, ?, ?, ?)",
                call_rows,
            )
            cur.execute(
                "INSERT INTO applied_txns (txn_id, file, ts) VALUES (?, ?, ?)",
                (txn_id, file_path, ts),
            )
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

    def list_applied_txns(self) -> list[str]:
        cur = self.conn.cursor()
        rows = cur.execute("SELECT txn_id FROM applied_txns ORDER BY ts, txn_id").fetchall()
        return [txn_id for (txn_id,) in rows]

    def cleanup_applied_txns(self, retention_seconds: float, *, now: Optional[float] = None) -> int:
        cutoff = (time.time() if now is None else now) - retention_seconds
        cur = self.conn.cursor()
        cur.execute("DELETE FROM applied_txns WHERE ts < ?", (cutoff,))
        self.conn.commit()
        return cur.rowcount

    def list_symbols(self, path: Union[str, Path, None] = None) -> List[Symbol]:
        cur = self.conn.cursor()
        if path is None:
            rows = cur.execute("SELECT name, kind, file, line FROM symbols ORDER BY file, line").fetchall()
        else:
            rows = cur.execute(
                "SELECT name, kind, file, line FROM symbols WHERE file = ? ORDER BY line",
                (str(Path(path)),),
            ).fetchall()
        return [Symbol(name, kind, file, line) for name, kind, file, line in rows]

    def search_symbols(self, query: str, limit: int = 10, fuzzy: bool = True) -> List[Symbol]:
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
        normalized_query = query.strip()
        if not normalized_query or not self._symbol_fts_enabled:
            return []

        fts_query = self._build_fts_query(normalized_query)
        if fts_query is None:
            return []

        sql = """
        WITH degree AS (
            SELECT name, COUNT(*) AS deg
            FROM (
                SELECT caller AS name FROM calls
                UNION ALL
                SELECT callee AS name FROM calls
            )
            GROUP BY name
        )
        SELECT
            s.name,
            s.kind,
            s.file,
            s.line,
            bm25(symbol_fts) AS fts_rank,
            COALESCE(d.deg, 0) AS degree
        FROM symbol_fts
        JOIN symbols AS s ON s.rowid = symbol_fts.rowid
        LEFT JOIN degree AS d ON d.name = s.name
        WHERE symbol_fts MATCH ?
        """
        params: list[object] = [fts_query]
        if exclude_name:
            sql += " AND s.name != ?"
            params.append(exclude_name)

        sql += """
        ORDER BY
            bm25(symbol_fts) ASC,
            COALESCE(d.deg, 0) DESC,
            length(s.name) ASC,
            s.name ASC,
            s.file ASC,
            s.line ASC
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

    def find_callers(self, callee: str, limit: int = 50) -> List[CallSite]:
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT caller, callee, file, line FROM calls WHERE callee = ? ORDER BY file, line LIMIT ?",
            (callee, limit),
        ).fetchall()
        return [CallSite(caller, callee_name, file, line) for caller, callee_name, file, line in rows]

    def find_callees(self, caller: str, limit: int = 50) -> List[CallSite]:
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT caller, callee, file, line FROM calls WHERE caller = ? ORDER BY file, line LIMIT ?",
            (caller, limit),
        ).fetchall()
        return [CallSite(caller_name, callee, file, line) for caller_name, callee, file, line in rows]
