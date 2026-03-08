import json
from pathlib import Path
from types import SimpleNamespace

from plugins.atlas_indexer.graph_store import GraphStore
from plugins.atlas_indexer.indexer import AtlasIndexer
from plugins.atlas_indexer.tailer_bridge import AtlasTailerBridge
from plugins.journal_tailer import JournalTailer


def _append_record(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def test_bridge_indexes_only_after_commit(tmp_path: Path):
    workspace_root = tmp_path
    source_path = workspace_root / "tracked.py"
    source_path.write_text("def task():\n    return 1\n", encoding="utf-8")

    journal_path = workspace_root / ".antigravity" / "memory" / "journal.jsonl"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    graph = GraphStore(workspace_root / ".antigravity" / "atlas" / "atlas.db")
    indexer = AtlasIndexer(workspace_root=workspace_root, graph_store=graph)
    indexer.coalesce_window_seconds = 0.0
    tailer = JournalTailer(journal_path)
    bridge = AtlasTailerBridge(tailer, indexer)

    _append_record(
        journal_path,
        {
            "type": "intent",
            "txn_id": "txn-1",
            "ts": 1.0,
            "target": "tracked.py",
            "op": "update_node",
            "node": {"node_id": "task"},
            "old_hash": "before",
        },
    )

    assert bridge.pump() == []
    assert graph.list_symbols(source_path) == []

    _append_record(journal_path, {"type": "commit", "txn_id": "txn-1", "ts": 2.0, "new_hash": "after"})

    assert bridge.pump() == ["tracked.py"]
    assert [symbol.name for symbol in graph.list_symbols(source_path)] == ["task"]


def test_bridge_factory_uses_workspace_defaults(tmp_path: Path):
    source_path = tmp_path / "nested.py"
    source_path.write_text("class Demo:\n    pass\n", encoding="utf-8")

    journal_path = tmp_path / ".antigravity" / "memory" / "journal.jsonl"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    bridge = AtlasTailerBridge.from_workspace(tmp_path)
    bridge.indexer.coalesce_window_seconds = 0.0

    _append_record(
        journal_path,
        {
            "type": "intent",
            "txn_id": "txn-2",
            "ts": 1.0,
            "target": "nested.py",
            "op": "update_node",
            "node": {"node_id": "demo"},
            "old_hash": "old",
        },
    )
    _append_record(journal_path, {"type": "commit", "txn_id": "txn-2", "ts": 2.0, "new_hash": "new"})

    assert bridge.pump() == ["nested.py"]
    assert [symbol.name for symbol in bridge.indexer.graph.list_symbols(source_path)] == ["Demo"]


def test_bridge_replay_skips_duplicate_txn(tmp_path: Path):
    source_path = tmp_path / "tracked.py"
    source_path.write_text("def task():\n    return 1\n", encoding="utf-8")

    graph = GraphStore(tmp_path / ".antigravity" / "atlas" / "atlas.db")
    indexer = AtlasIndexer(workspace_root=tmp_path, graph_store=graph)
    indexer.coalesce_window_seconds = 0.0
    tailer = JournalTailer(tmp_path / ".antigravity" / "memory" / "journal.jsonl")
    bridge = AtlasTailerBridge(tailer, indexer)
    replay_event = SimpleNamespace(txn={"txn_id": "txn-1", "ts": 1.0, "target": "tracked.py"})

    bridge.indexer.handle_event(replay_event)
    assert bridge.indexer.poll() == ["tracked.py"]

    bridge.indexer.handle_event(replay_event)
    assert bridge.indexer.poll() == []
    assert graph.list_applied_txns() == ["txn-1"]


def test_run_forever_sleeps_only_when_idle(tmp_path: Path, monkeypatch):
    journal_path = tmp_path / ".antigravity" / "memory" / "journal.jsonl"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    bridge = AtlasTailerBridge(JournalTailer(journal_path), AtlasIndexer(workspace_root=tmp_path))

    sleep_calls = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        raise RuntimeError("stop")

    monkeypatch.setattr("plugins.atlas_indexer.tailer_bridge.time.sleep", fake_sleep)

    try:
        bridge.run_forever(poll_interval=0.25)
    except RuntimeError as exc:
        assert str(exc) == "stop"

    assert sleep_calls == [0.25]
