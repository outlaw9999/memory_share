"""
Unit tests for JournalTailer plugin.

Verifies:
- Event parsing correctness
- Batch accumulation timing
- Subscriber notification
- File position tracking (append-only read)
"""

import json
import time
import tempfile
from pathlib import Path
from unittest.mock import Mock

from plugins.journal_tailer import JournalTailer, EventType, JournalEvent


def test_parse_event():
    """Test parsing a single journal line."""
    tailer = JournalTailer()

    # Valid event
    line = json.dumps({
        "event_type": "node_created",
        "timestamp": time.time(),
        "node_id": "anchor#section-1",
        "data": {"content": "test"}
    })
    event = tailer._parse_event(line, 1)
    assert event is not None
    assert event.event_type == EventType.NODE_CREATED
    assert event.node_id == "anchor#section-1"

    # Invalid JSON
    assert tailer._parse_event("not valid json", 2) is None

    # Unknown event type
    line_bad_type = json.dumps({
        "event_type": "unknown_event",
        "timestamp": time.time()
    })
    assert tailer._parse_event(line_bad_type, 3) is None


def test_batch_accumulation():
    """Test that events accumulate and batch emits on timer."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_path = Path(tmpdir) / "journal.jsonl"
        journal_path.write_text("")

        tailer = JournalTailer(
            journal_path=journal_path,
            batch_interval_ms=100,  # 100ms for test speed
        )

        # Setup subscriber
        events_received = []
        tailer.subscribe(EventType.NODE_CREATED, lambda e: events_received.append(e))

        tailer.start()

        # Write 5 events to journal
        for i in range(5):
            line = json.dumps({
                "event_type": "node_created",
                "timestamp": time.time(),
                "node_id": f"anchor#sec-{i}",
                "data": {"index": i}
            })
            journal_path.write_text(journal_path.read_text() + line + "\n")

        # First tick: accumulate events
        tailer.tick()
        assert len(events_received) == 0  # No emit yet (< 100ms)
        assert len(tailer.pending_events) == 5

        # Wait for batch interval
        time.sleep(0.15)

        # Second tick: emit batch
        tailer.tick()
        assert len(events_received) == 5  # All emitted
        assert len(tailer.pending_events) == 0

        tailer.stop()


def test_append_only_read():
    """Test that tailer only reads newly appended lines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_path = Path(tmpdir) / "journal.jsonl"

        # Write initial 3 lines
        lines = []
        for i in range(3):
            line = json.dumps({
                "event_type": "node_created",
                "timestamp": time.time(),
                "node_id": f"anchor#sec-{i}",
                "data": {"index": i}
            })
            lines.append(line)
        journal_path.write_text("\n".join(lines) + "\n")

        tailer = JournalTailer(journal_path=journal_path)

        # First read gets 3 events
        events1 = tailer._read_new_entries()
        assert len(events1) == 3

        # File position stored
        pos_after_first = tailer.last_position

        # Append 2 more lines
        new_lines = []
        for i in range(3, 5):
            line = json.dumps({
                "event_type": "node_created",
                "timestamp": time.time(),
                "node_id": f"anchor#sec-{i}",
                "data": {"index": i}
            })
            new_lines.append(line)
        journal_path.write_text(journal_path.read_text() + "\n".join(new_lines) + "\n")

        # Second read gets only 2 new events (O(1)!)
        events2 = tailer._read_new_entries()
        assert len(events2) == 2
        assert events2[0].data["index"] == 3
        assert events2[1].data["index"] == 4


def test_max_batch_size_forcing_emit():
    """Test that large batches force emit even before interval."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_path = Path(tmpdir) / "journal.jsonl"
        journal_path.write_text("")

        tailer = JournalTailer(
            journal_path=journal_path,
            batch_interval_ms=5000,  # Long interval
            max_batch_size=3,  # But force emit at 3 events
        )

        events_received = []
        tailer.subscribe(EventType.NODE_CREATED, lambda e: events_received.append(e))

        # Write 5 events quickly
        for i in range(5):
            line = json.dumps({
                "event_type": "node_created",
                "timestamp": time.time(),
                "node_id": f"anchor#sec-{i}",
                "data": {"index": i}
            })
            journal_path.write_text(journal_path.read_text() + line + "\n")

        tailer.tick()  # Reads 5 events

        # Should emit first batch of 3 (max_batch_size reached)
        assert len(events_received) == 3
        # Remainder pending
        assert len(tailer.pending_events) == 2


def test_status_tracking():
    """Test that status dictionary is updated correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_path = Path(tmpdir) / "journal.jsonl"
        journal_path.write_text("")

        tailer = JournalTailer(journal_path=journal_path, batch_interval_ms=50)

        # Write 2 events
        for i in range(2):
            line = json.dumps({
                "event_type": "node_created",
                "timestamp": time.time(),
                "node_id": f"anchor#sec-{i}",
            })
            journal_path.write_text(journal_path.read_text() + line + "\n")

        tailer.start()
        tailer.tick()

        assert tailer.status["is_running"] == True
        assert tailer.status["events_processed"] == 0  # Not emitted yet
        assert tailer.status["current_batch_size"] == 2

        time.sleep(0.1)
        tailer.tick()

        assert tailer.status["events_processed"] == 2  # Emitted
        assert tailer.status["batches_emitted"] == 1


if __name__ == "__main__":
    test_parse_event()
    test_batch_accumulation()
    test_append_only_read()
    test_max_batch_size_forcing_emit()
    test_status_tracking()
    print("✅ All tests passed!")
