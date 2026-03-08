import json
from pathlib import Path

from plugins.journal_tailer import EventType, JournalTailer


def _append_record(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def test_emits_only_after_commit(tmp_path: Path):
    journal_path = tmp_path / "journal.jsonl"
    tailer = JournalTailer(journal_path)
    received = []
    tailer.subscribe(received.append)

    _append_record(
        journal_path,
        {
            "type": "intent",
            "txn_id": "txn-1",
            "ts": 1.0,
            "agent": "alpha",
            "target": "brain/auth.md",
            "op": "update_node",
            "node": {"node_id": "auth"},
            "old_hash": "abc",
        },
    )

    tailer.poll()
    assert received == []

    _append_record(
        journal_path,
        {
            "type": "commit",
            "txn_id": "txn-1",
            "ts": 2.0,
            "new_hash": "def",
        },
    )

    tailer.poll()

    assert len(received) == 1
    assert received[0].event_type is EventType.NODE_UPDATED
    assert received[0].txn["node"]["node_id"] == "auth"
    assert received[0].txn_id == "txn-1"


def test_rollback_discards_pending_transaction(tmp_path: Path):
    journal_path = tmp_path / "journal.jsonl"
    tailer = JournalTailer(journal_path)
    received = []
    tailer.subscribe(received.append)

    _append_record(journal_path, {"type": "intent", "txn_id": "txn-1", "ts": 1.0, "node": {"node_id": "n1"}})
    _append_record(journal_path, {"type": "rollback", "txn_id": "txn-1", "ts": 2.0, "reason": "conflict"})
    _append_record(journal_path, {"type": "commit", "txn_id": "txn-1", "ts": 3.0, "new_hash": "ignored"})

    tailer.poll()

    assert received == []
    assert tailer._pending == {}


def test_torn_line_is_retried_without_advancing_offset(tmp_path: Path):
    journal_path = tmp_path / "journal.jsonl"
    tailer = JournalTailer(journal_path)
    received = []
    tailer.subscribe(received.append)

    with journal_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "intent", "txn_id": "txn-1", "ts": 1.0, "node": {"node_id": "n1"}}) + "\n")
        handle.write('{"type":"commit","txn_id":"txn-1"')

    tailer.poll()
    offset_after_partial = tailer.offset
    assert received == []
    assert "txn-1" in tailer._pending

    with journal_path.open("a", encoding="utf-8") as handle:
        handle.write(',"ts":2.0,"new_hash":"hash"}\n')

    tailer.poll()

    assert tailer.offset > offset_after_partial
    assert len(received) == 1
    assert received[0].txn_id == "txn-1"


def test_truncation_resets_offset_and_pending_state(tmp_path: Path):
    journal_path = tmp_path / "journal.jsonl"
    tailer = JournalTailer(journal_path)

    _append_record(journal_path, {"type": "intent", "txn_id": "txn-1", "ts": 1.0, "node": {"node_id": "n1"}})
    tailer.poll()
    assert tailer.offset > 0
    assert "txn-1" in tailer._pending

    journal_path.write_text("", encoding="utf-8")
    tailer.poll()

    assert tailer.offset == 0
    assert tailer._pending == {}


def test_commit_without_matching_intent_is_ignored(tmp_path: Path):
    journal_path = tmp_path / "journal.jsonl"
    tailer = JournalTailer(journal_path)
    received = []
    tailer.subscribe(received.append)

    _append_record(journal_path, {"type": "commit", "txn_id": "txn-missing", "ts": 1.0, "new_hash": "x"})
    tailer.poll()

    assert received == []
