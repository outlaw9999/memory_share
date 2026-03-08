import sqlite3
from pathlib import Path

from plugins.atlas_indexer.graph_store import GraphStore
from plugins.atlas_indexer.indexer import AtlasIndexer
from plugins.atlas_indexer.models import CallSite, Symbol
from plugins.atlas_indexer.scanner import Scanner


class FakeEvent:
    def __init__(self, txn):
        self.txn = txn


def test_scanner_extracts_python_symbols(tmp_path: Path):
    source_path = tmp_path / "sample.py"
    source_path.write_text(
        "import os\nfrom pathlib import Path\n\nclass Demo:\n    pass\n\ndef run():\n    return 1\n",
        encoding="utf-8",
    )

    symbols = Scanner().scan_file(source_path)

    assert [symbol.kind for symbol in symbols] == ["import", "import", "class", "function"]
    assert [symbol.name for symbol in symbols] == ["os", "pathlib.Path", "Demo", "run"]


def test_graph_store_replaces_symbols_for_a_file(tmp_path: Path):
    db_path = tmp_path / "atlas.db"
    source_path = tmp_path / "file.py"
    source_path.write_text("def first():\n    pass\n", encoding="utf-8")

    store = GraphStore(db_path)
    scanner = Scanner()
    store.update_file(source_path, scanner.scan_file(source_path))
    assert [symbol.name for symbol in store.list_symbols(source_path)] == ["first"]

    source_path.write_text("def second():\n    pass\n", encoding="utf-8")
    store.update_file(source_path, scanner.scan_file(source_path))

    assert [symbol.name for symbol in store.list_symbols(source_path)] == ["second"]


def test_graph_store_skips_duplicate_txn_replay(tmp_path: Path):
    db_path = tmp_path / "atlas.db"
    source_path = tmp_path / "file.py"
    source_path.write_text("def once():\n    pass\n", encoding="utf-8")

    store = GraphStore(db_path)
    symbols = Scanner().scan_file(source_path)

    assert store.update_file(source_path, symbols, txn_id="txn-1", ts=1.0) is True
    assert store.update_file(source_path, symbols, txn_id="txn-1", ts=1.0) is False
    assert [symbol.name for symbol in store.list_symbols(source_path)] == ["once"]
    assert store.list_applied_txns() == ["txn-1"]


def test_indexer_marks_dirty_once_and_indexes_on_poll(tmp_path: Path):
    source_path = tmp_path / "tracked.py"
    source_path.write_text("def task():\n    return 1\n", encoding="utf-8")

    graph = GraphStore(tmp_path / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=graph)
    indexer.coalesce_window_seconds = 0.0

    event = FakeEvent({"target": "tracked.py", "node": {"node_id": "x"}})
    indexer.handle_event(event)
    indexer.handle_event(event)

    processed = indexer.poll()

    assert processed == ["tracked.py"]
    assert [symbol.name for symbol in graph.list_symbols(source_path)] == ["task"]
    assert indexer.dirty_files == set()


def test_indexer_accepts_node_path_events(tmp_path: Path):
    source_path = tmp_path / "nested.py"
    source_path.write_text("class Item:\n    pass\n", encoding="utf-8")

    graph = GraphStore(tmp_path / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=graph)
    indexer.coalesce_window_seconds = 0.0
    event = FakeEvent({"node": {"path": "nested.py"}})

    indexer.handle_event(event)
    indexer.poll()

    assert [symbol.name for symbol in graph.list_symbols(source_path)] == ["Item"]


def test_indexer_skips_duplicate_replayed_txn(tmp_path: Path):
    source_path = tmp_path / "tracked.py"
    source_path.write_text("def task():\n    return 1\n", encoding="utf-8")

    graph = GraphStore(tmp_path / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=graph)
    indexer.coalesce_window_seconds = 0.0
    event = FakeEvent({"txn_id": "txn-1", "ts": 1.0, "target": "tracked.py", "node": {"node_id": "task"}})

    indexer.handle_event(event)
    assert indexer.poll() == ["tracked.py"]

    indexer.handle_event(event)
    assert indexer.poll() == []
    assert [symbol.name for symbol in graph.list_symbols(source_path)] == ["task"]


def test_indexer_retries_when_file_changes_during_scan(tmp_path: Path):
    source_path = tmp_path / "tracked.py"
    source_path.write_text("def before():\n    return 1\n", encoding="utf-8")

    class FlakyScanner:
        def __init__(self):
            self._mutated = False
            self._scanner = Scanner()

        def scan_file(self, path: Path):
            symbols = self._scanner.scan_file(path)
            if not self._mutated:
                self._mutated = True
                Path(path).write_text("def after():\n    return 2\n", encoding="utf-8")
            return symbols

    graph = GraphStore(tmp_path / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=graph, scanner=FlakyScanner())
    indexer.coalesce_window_seconds = 0.0
    event = FakeEvent({"txn_id": "txn-1", "ts": 1.0, "target": "tracked.py"})

    indexer.handle_event(event)
    assert indexer.poll() == []
    assert "tracked.py" in indexer.dirty_files

    assert indexer.poll() == ["tracked.py"]
    assert [symbol.name for symbol in graph.list_symbols(source_path)] == ["after"]


def test_graph_store_cleans_up_expired_txns(tmp_path: Path):
    db_path = tmp_path / "atlas.db"
    source_path = tmp_path / "file.py"
    source_path.write_text("def once():\n    pass\n", encoding="utf-8")

    store = GraphStore(db_path)
    symbols = Scanner().scan_file(source_path)
    store.update_file(source_path, symbols, txn_id="txn-old", ts=10.0)
    store.update_file(source_path, symbols, txn_id="txn-new", ts=20.0)

    deleted = store.cleanup_applied_txns(5.0, now=20.0)

    assert deleted == 1
    assert store.list_applied_txns() == ["txn-new"]


def test_graph_store_search_symbols_supports_prefix_and_fuzzy_fallback(tmp_path: Path):
    db_path = tmp_path / "atlas.db"
    store = GraphStore(db_path)
    source_path = tmp_path / "file.py"

    store.update_file(
        source_path,
        [
            Symbol("write_memory", "function", str(source_path), 1),
            Symbol("kernel_write", "function", str(source_path), 2),
        ],
    )

    assert [symbol.name for symbol in store.search_symbols("write_mem", fuzzy=False)] == ["write_memory"]
    assert [symbol.name for symbol in store.search_symbols("rite_mem", fuzzy=True)] == ["write_memory"]


def test_graph_store_rebuilds_symbol_fts_for_existing_symbols(tmp_path: Path):
    db_path = tmp_path / "atlas.db"
    source_path = tmp_path / "legacy.py"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE symbols (
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            file TEXT NOT NULL,
            line INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
        ("kernel_store", "function", str(source_path), 3),
    )
    conn.commit()
    conn.close()

    store = GraphStore(db_path)

    assert [symbol.name for symbol in store.search_symbols("kernel_st", fuzzy=False)] == ["kernel_store"]


def test_graph_store_migrates_symbol_fts_to_prefix_index(tmp_path: Path):
    db_path = tmp_path / "atlas.db"
    source_path = tmp_path / "legacy.py"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE symbols (
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            file TEXT NOT NULL,
            line INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
        ("write_memory", "function", str(source_path), 7),
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE symbol_fts
        USING fts5(name, content='symbols', content_rowid='rowid')
        """
    )
    conn.execute("INSERT INTO symbol_fts(symbol_fts) VALUES ('rebuild')")
    conn.commit()
    conn.close()

    store = GraphStore(db_path)
    fts_sql = store.conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'symbol_fts'"
    ).fetchone()[0]

    assert "prefix='2 3'" in fts_sql
    assert "tokenize='unicode61'" in fts_sql
    assert [symbol.name for symbol in store.search_symbols("write_mem", fuzzy=False)] == ["write_memory"]


def test_graph_store_find_callers_uses_covering_index(tmp_path: Path):
    db_path = tmp_path / "atlas.db"
    store = GraphStore(db_path)
    cur = store.conn.cursor()
    cur.executemany(
        "INSERT INTO calls (caller, callee, file, line) VALUES (?, ?, ?, ?)",
        [
            ("run", "helper", "b.py", 20),
            ("main", "helper", "a.py", 10),
            ("skip", "other", "c.py", 30),
        ],
    )
    store.conn.commit()

    plan = cur.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT caller, callee, file, line
        FROM calls
        WHERE callee = ?
        ORDER BY file, line
        LIMIT ?
        """,
        ("helper", 50),
    ).fetchall()

    assert any("USING COVERING INDEX idx_calls_callee_cover" in detail for *_, detail in plan)
    assert not any("USE TEMP B-TREE FOR ORDER BY" in detail for *_, detail in plan)
    assert [(call.caller, call.file, call.line) for call in store.find_callers("helper")] == [
        ("main", "a.py", 10),
        ("run", "b.py", 20),
    ]


def test_graph_store_find_callees_uses_covering_index(tmp_path: Path):
    db_path = tmp_path / "atlas.db"
    store = GraphStore(db_path)
    cur = store.conn.cursor()
    cur.executemany(
        "INSERT INTO calls (caller, callee, file, line) VALUES (?, ?, ?, ?)",
        [
            ("main", "helper", "a.py", 10),
            ("main", "helper_two", "b.py", 20),
            ("other", "skip", "c.py", 30),
        ],
    )
    store.conn.commit()

    plan = cur.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT caller, callee, file, line
        FROM calls
        WHERE caller = ?
        ORDER BY file, line
        LIMIT ?
        """,
        ("main", 50),
    ).fetchall()

    assert any("USING COVERING INDEX idx_calls_caller_cover" in detail for *_, detail in plan)
    assert not any("USE TEMP B-TREE FOR ORDER BY" in detail for *_, detail in plan)
    assert [(call.callee, call.file, call.line) for call in store.find_callees("main")] == [
        ("helper", "a.py", 10),
        ("helper_two", "b.py", 20),
    ]


def test_indexer_waits_for_coalescing_window(tmp_path: Path):
    source_path = tmp_path / "tracked.py"
    source_path.write_text("def task():\n    return 1\n", encoding="utf-8")

    graph = GraphStore(tmp_path / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=graph)
    indexer.coalesce_window_seconds = 0.2
    event = FakeEvent({"target": "tracked.py"})

    indexer.handle_event(event)
    assert indexer.poll() == []
    assert "tracked.py" in indexer.dirty_files

    indexer._dirty_seen_at["tracked.py"] -= 0.3
    assert indexer.poll() == ["tracked.py"]


def test_indexer_prunes_missing_dirty_paths(tmp_path: Path):
    source_path = tmp_path / "deleted.py"
    source_path.write_text("def gone():\n    pass\n", encoding="utf-8")

    graph = GraphStore(tmp_path / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=graph)
    indexer.coalesce_window_seconds = 0.0
    event = FakeEvent({"txn_id": "txn-1", "ts": 1.0, "target": "deleted.py"})

    indexer.handle_event(event)
    source_path.unlink()

    assert indexer.poll() == []
    assert "deleted.py" not in indexer.dirty_files
    assert "deleted.py" not in indexer._dirty_seen_at
    assert "deleted.py" not in indexer._dirty_txns
