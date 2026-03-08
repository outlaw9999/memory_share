from pathlib import Path

from plugins.atlas_indexer.graph_store import GraphStore
from plugins.atlas_indexer.indexer import AtlasIndexer
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
    event = FakeEvent({"node": {"path": "nested.py"}})

    indexer.handle_event(event)
    indexer.poll()

    assert [symbol.name for symbol in graph.list_symbols(source_path)] == ["Item"]


def test_indexer_skips_duplicate_replayed_txn(tmp_path: Path):
    source_path = tmp_path / "tracked.py"
    source_path.write_text("def task():\n    return 1\n", encoding="utf-8")

    graph = GraphStore(tmp_path / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=graph)
    event = FakeEvent({"txn_id": "txn-1", "ts": 1.0, "target": "tracked.py", "node": {"node_id": "task"}})

    indexer.handle_event(event)
    assert indexer.poll() == ["tracked.py"]

    indexer.handle_event(event)
    assert indexer.poll() == []
    assert [symbol.name for symbol in graph.list_symbols(source_path)] == ["task"]
