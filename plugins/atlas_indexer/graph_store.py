import sqlite3
from pathlib import Path
from typing import Iterable, List, Union

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
        cur.execute("CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)")
        self.conn.commit()

    def update_file(self, path: Union[str, Path], symbols: Iterable[Symbol]) -> None:
        file_path = str(Path(path))
        cur = self.conn.cursor()
        cur.execute("DELETE FROM symbols WHERE file = ?", (file_path,))
        cur.executemany(
            "INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
            [(symbol.name, symbol.kind, symbol.file, symbol.line) for symbol in symbols],
        )
        self.conn.commit()

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
