import json
import logging
import os
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


def test_out_of_order_commit_logs_warning_and_keeps_wal_order(tmp_path: Path, caplog):
    journal_path = tmp_path / "journal.jsonl"
    tailer = JournalTailer(journal_path)
    received = []
    tailer.subscribe(received.append)

    _append_record(journal_path, {"type": "intent", "txn_id": "txn-1", "ts": 1.0, "node": {"node_id": "n1"}})
    _append_record(journal_path, {"type": "intent", "txn_id": "txn-2", "ts": 2.0, "node": {"node_id": "n2"}})
    _append_record(journal_path, {"type": "commit", "txn_id": "txn-2", "ts": 20.0, "new_hash": "h2"})
    _append_record(journal_path, {"type": "commit", "txn_id": "txn-1", "ts": 10.0, "new_hash": "h1"})

    with caplog.at_level(logging.WARNING):
        tailer.poll()

    assert [event.txn_id for event in received] == ["txn-2", "txn-1"]
    assert "Out-of-order commit detected" in caplog.text


def test_restart_restores_pending_state_and_resumes_commit(tmp_path: Path):
    journal_path = tmp_path / "journal.jsonl"
    state_path = tmp_path / "journal.offset.json"

    first_tailer = JournalTailer(journal_path, state_path=state_path)
    _append_record(journal_path, {"type": "intent", "txn_id": "txn-1", "ts": 1.0, "node": {"node_id": "n1"}})
    first_tailer.poll()

    assert state_path.exists()

    restarted_tailer = JournalTailer(journal_path, state_path=state_path)
    received = []
    restarted_tailer.subscribe(received.append)

    _append_record(journal_path, {"type": "commit", "txn_id": "txn-1", "ts": 2.0, "new_hash": "h1"})
    restarted_tailer.poll()

    assert [event.txn_id for event in received] == ["txn-1"]


def test_rotation_detects_new_file_identity_and_restarts_from_zero(tmp_path: Path):
    journal_path = tmp_path / "journal.jsonl"
    state_path = tmp_path / "journal.offset.json"
    tailer = JournalTailer(journal_path, state_path=state_path)
    received = []
    tailer.subscribe(received.append)

    _append_record(journal_path, {"type": "intent", "txn_id": "txn-old", "ts": 1.0, "node": {"node_id": "old"}})
    tailer.poll()
    old_offset = tailer.offset
    assert "txn-old" in tailer._pending

    replacement_path = tmp_path / "journal.replacement.jsonl"
    _append_record(replacement_path, {"type": "intent", "txn_id": "txn-new", "ts": 2.0, "node": {"node_id": "new"}})
    _append_record(replacement_path, {"type": "commit", "txn_id": "txn-new", "ts": 3.0, "new_hash": "h2"})
    assert replacement_path.stat().st_size >= old_offset

    os.replace(replacement_path, journal_path)
    tailer.poll()

    assert [event.txn_id for event in received] == ["txn-new"]
    assert tailer._pending == {}
