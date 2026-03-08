import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional, Union

from .models import Symbol


class GraphStore:
    def __init__(self, db_path: Union[str, Path] = ".antigravity/atlas/atlas.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
        cur.execute("CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_applied_txns_ts ON applied_txns(ts)")
        self.conn.commit()

    def update_file(
        self,
        path: Union[str, Path],
        symbols: Iterable[Symbol],
        *,
        txn_id: Optional[str] = None,
        ts: Optional[float] = None,
    ) -> bool:
        file_path = str(Path(path))
        symbol_rows = [(symbol.name, symbol.kind, symbol.file, symbol.line) for symbol in symbols]
        if txn_id is not None:
            return self._apply_once(file_path, symbol_rows, txn_id, ts or 0.0)

        cur = self.conn.cursor()
        cur.execute("DELETE FROM symbols WHERE file = ?", (file_path,))
        cur.executemany(
            "INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
            symbol_rows,
        )
        self.conn.commit()
        return True

    def _apply_once(self, file_path: str, symbol_rows: list[tuple[str, str, str, int]], txn_id: str, ts: float) -> bool:
        cur = self.conn.cursor()
        cur.execute("BEGIN")
        try:
            row = cur.execute("SELECT 1 FROM applied_txns WHERE txn_id = ?", (txn_id,)).fetchone()
            if row is not None:
                self.conn.rollback()
                return False

            cur.execute("DELETE FROM symbols WHERE file = ?", (file_path,))
            cur.executemany(
                "INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
                symbol_rows,
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
