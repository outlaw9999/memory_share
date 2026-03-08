"""
JournalTailer: Non-blocking journal stream reader for Antigravity kernel.

Core Design Principles:
- O(1) read operations: Only process new lines appended to journal.jsonl
- Batch indexing: Accumulate events over 500ms window, update index once
- Zero-copy semantics: Pass references, not copies, to event subscribers
- Transparent to kernel: Tailer operates independently of write_memory()

Architecture:
```
journal.jsonl (WAL)
    ↓
JournalTailer.read() [500ms batch]
    ↓
EventBus.emit(node_created, node_updated, node_deleted)
    ↓
ATLAS indexer / Telemetry / Other plugins
```
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib


class EventType(str, Enum):
    """Journal event types."""
    NODE_CREATED = "node_created"
    NODE_UPDATED = "node_updated"
    NODE_DELETED = "node_deleted"
    TRANSACTION_INTENT = "transaction_intent"
    TRANSACTION_COMMIT = "transaction_commit"
    OCC_CONFLICT = "occ_conflict"


@dataclass
class JournalEvent:
    """Represents a parsed journal event."""
    event_type: EventType
    timestamp: float
    node_id: Optional[str]
    data: Optional[Dict[str, Any]]
    raw_line: str
    line_number: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "node_id": self.node_id,
            "data": self.data,
            "line_number": self.line_number,
        }


class JournalTailer:
    """
    Non-blocking journal stream reader.
    
    Reads journal.jsonl in batches, accumulating events for 500ms
    before emitting to subscribers. This prevents thrashing the event bus
    while maintaining sub-second latency for critical operations.
    """

    def __init__(
        self,
        journal_path: Optional[Path] = None,
        batch_interval_ms: int = 500,
        max_batch_size: int = 1000,
    ):
        """
        Initialize JournalTailer.

        Args:
            journal_path: Path to journal.jsonl (default: .antigravity/memory/journal.jsonl)
            batch_interval_ms: Accumulate events for this duration before emit (default: 500ms)
            max_batch_size: Force emit if batch reaches this size (default: 1000 events)
        """
        if journal_path is None:
            journal_path = Path(".antigravity/memory/journal.jsonl")

        self.journal_path = journal_path
        self.batch_interval_ms = batch_interval_ms
        self.max_batch_size = max_batch_size

        # Tracking state
        self.last_position = 0
        self.last_read_time = time.time()
        self.pending_events: List[JournalEvent] = []

        # Event subscribers: event_type -> [callback, callback, ...]
        self._subscribers: Dict[EventType, List[Callable]] = {
            event_type: [] for event_type in EventType
        }

        # Status tracking
        self.status = {
            "is_running": False,
            "events_processed": 0,
            "batches_emitted": 0,
            "last_batch_time": None,
            "current_batch_size": 0,
        }

    def subscribe(self, event_type: EventType, callback: Callable[[JournalEvent], None]) -> None:
        """
        Subscribe to journal events.

        Args:
            event_type: Type of event to listen for
            callback: Function to call when event is emitted
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Unsubscribe from journal events."""
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)

    def _parse_event(self, line: str, line_number: int) -> Optional[JournalEvent]:
        """
        Parse a single journal line into a JournalEvent.

        Returns None if line is not a valid journal entry.
        """
        try:
            record = json.loads(line)
            event_type_str = record.get("event_type")

            # Try to match event type
            try:
                event_type = EventType(event_type_str)
            except ValueError:
                # Unknown event type, skip
                return None

            return JournalEvent(
                event_type=event_type,
                timestamp=record.get("timestamp", time.time()),
                node_id=record.get("node_id"),
                data=record.get("data"),
                raw_line=line,
                line_number=line_number,
            )
        except json.JSONDecodeError:
            # Invalid JSON, skip
            return None

    def _read_new_entries(self) -> List[JournalEvent]:
        """
        Read only new entries appended to journal.jsonl since last read.

        Uses file position tracking for O(1) append detection.
        Returns list of newly parsed events.
        """
        if not self.journal_path.exists():
            return []

        events = []
        try:
            with open(self.journal_path, "rb") as f:
                # Seek to last known position
                f.seek(self.last_position)

                line_number = self.last_position  # Simplified; true line number tracking is more complex
                for line in f:
                    try:
                        line_str = line.decode("utf-8").strip()
                        if line_str:
                            event = self._parse_event(line_str, line_number)
                            if event:
                                events.append(event)
                        line_number += 1
                    except UnicodeDecodeError:
                        continue

                # Update position for next read
                self.last_position = f.tell()
        except IOError:
            # Journal being written, skip this read
            pass

        return events

    def _emit_batch(self) -> None:
        """
        Emit all pending events to subscribers.

        Called either after batch_interval_ms or when batch reaches max_batch_size.
        """
        if not self.pending_events:
            return

        # Group events by type for efficient dispatch
        events_by_type: Dict[EventType, List[JournalEvent]] = {}
        for event in self.pending_events:
            if event.event_type not in events_by_type:
                events_by_type[event.event_type] = []
            events_by_type[event.event_type].append(event)

        # Call subscribers
        for event_type, events in events_by_type.items():
            for callback in self._subscribers.get(event_type, []):
                for event in events:
                    try:
                        callback(event)
                    except Exception as e:
                        # Log error but don't crash tailer
                        print(f"Error in callback for {event_type}: {e}")

        # Update status
        self.status["events_processed"] += len(self.pending_events)
        self.status["batches_emitted"] += 1
        self.status["last_batch_time"] = time.time()

        # Clear batch
        self.pending_events.clear()

    def tick(self) -> None:
        """
        Poll journal and emit batched events if interval exceeded.

        Call this regularly (e.g., in event loop) to keep tailer running.
        """
        # Read new entries
        new_events = self._read_new_entries()
        self.pending_events.extend(new_events)

        # Check if we should emit batch
        now = time.time()
        should_emit = (
            len(self.pending_events) > 0
            and (
                (now - self.last_read_time) * 1000 >= self.batch_interval_ms
                or len(self.pending_events) >= self.max_batch_size
            )
        )

        if should_emit:
            self._emit_batch()
            self.last_read_time = now

        self.status["current_batch_size"] = len(self.pending_events)

    def start(self) -> None:
        """Mark tailer as running."""
        self.status["is_running"] = True

    def stop(self) -> None:
        """Flush pending events and mark tailer as stopped."""
        self._emit_batch()
        self.status["is_running"] = False

    def get_status(self) -> Dict[str, Any]:
        """Return current tailer status."""
        return {
            **self.status,
            "journal_path": str(self.journal_path),
            "file_position": self.last_position,
        }
