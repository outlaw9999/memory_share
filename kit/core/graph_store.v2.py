import sqlite3
import time
import re
from pathlib import Path
from typing import Iterable, List, Optional, Union, Dict

from .models import CallSite, Symbol  # type: ignore[import-not-found]


class GraphStore:
    def __init__(self, db_path: Union[str, Path] = ".antigravity/atlas/atlas.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Supercharge SQLite
        self.conn.execute("PRAGMA busy_timeout=5000;")
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA temp_store=MEMORY;")

        # LRU Cache cho Symbol -> Node ID (Tốc độ x5)
        self._symbol_cache: Dict[str, int] = {}
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()

        # New V2 Schema
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY,
                symbol TEXT UNIQUE NOT NULL,
                kind TEXT,
                file_path TEXT,
                line_number INTEGER
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                layer INTEGER NOT NULL,
                weight REAL DEFAULT 1.0,
                FOREIGN KEY(source_id) REFERENCES nodes(id),
                FOREIGN KEY(target_id) REFERENCES nodes(id)
            )
        """)

        # Covering indices
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_edges_source_layer ON edges(source_id, layer)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_edges_target_layer ON edges(target_id, layer)"
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_symbol ON nodes(symbol)")

        self.conn.commit()

    def get_or_create_node(
        self,
        symbol_name: str,
        kind: Optional[str] = None,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
    ) -> int:
        """Biến tên Symbol thành Integer ID (O(1) nhờ Cache, O(log N) DB)"""
        if symbol_name in self._symbol_cache:
            return self._symbol_cache[symbol_name]

        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO nodes (symbol, kind, file_path, line_number) VALUES (?, ?, ?, ?)",
            (symbol_name, kind, file_path, line_number),
        )
        cur.execute("SELECT id FROM nodes WHERE symbol = ?", (symbol_name,))
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"Failed to get node id for {symbol_name}")
        node_id: int = row["id"]

        self._symbol_cache[symbol_name] = node_id
        return node_id

    def add_edge(
        self,
        source_symbol: str,
        target_symbol: str,
        layer: int = 0,
        weight: float = 1.0,
    ) -> None:
        src_id = self.get_or_create_node(source_symbol)
        tgt_id = self.get_or_create_node(target_symbol)

        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO edges (source_id, target_id, layer, weight) VALUES (?, ?, ?, ?)",
            (src_id, tgt_id, layer, weight),
        )

    def update_file(
        self,
        path: Union[str, Path],
        symbols: Iterable[Symbol],
        calls: Iterable[CallSite] = (),
    ) -> bool:
        """Cập nhật Graph khi file thay đổi"""
        file_path = str(Path(path))
        cur = self.conn.cursor()
        cur.execute("BEGIN")
        try:
            # 1. Tìm các symbol thuộc về file này
            cur.execute("SELECT id FROM nodes WHERE file_path = ?", (file_path,))
            file_node_ids = [r["id"] for r in cur.fetchall()]

            # 2. Xóa các cạnh xuất phát từ các symbol này
            if file_node_ids:
                placeholders = ",".join(["?"] * len(file_node_ids))
                cur.execute(
                    f"DELETE FROM edges WHERE source_id IN ({placeholders})",
                    file_node_ids,
                )
                cur.execute("DELETE FROM nodes WHERE file_path = ?", (file_path,))

            # Xóa cache tránh ID bị stale
            self._symbol_cache.clear()

            # 3. Chèn lại các Symbol mới
            for sym in symbols:
                self.get_or_create_node(sym.name, sym.kind, sym.file, sym.line)

            # 4. Chèn lại các Edges (Call Graph -> layer 0)
            for call in calls:
                self.add_edge(call.caller, call.callee, layer=0)

            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

    def search_symbols(self, query: str, limit: int = 10) -> List[Symbol]:
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT symbol as name, kind, file_path as file, line_number as line FROM nodes WHERE symbol LIKE ? LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [Symbol(r["name"], r["kind"], r["file"], r["line"]) for r in rows]

    def close(self) -> None:
        self.conn.close()
