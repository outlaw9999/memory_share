"""
JournalTailer: WAL-aware journal stream reader for Antigravity Phase 6 kernel.

Architecture:
    journal.jsonl (intent/commit/rollback WAL)
           ↓
    JournalTailer.poll() [read new entries]
           ↓
    TransactionBuffer { pending[txn_id]: intent_record }
           ↓
    emit NODE_UPDATED [only on commit]
           ↓
    Subscribers (ATLAS, Telemetry, Vectorizer)

Design:
- O(1) poll: Only read appended lines
- WAL-native: Parses intent|commit|rollback, not events
- Silent failure proof: Only emits when txn commits
- Torn line safe: Detects partial JSON and waits for next poll
- Truncation resilient: Resets offset on file shrink
"""

import json
import os
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Callable, List, Optional


class EventType(Enum):
    """Semantic events derived from WAL transactions."""
    NODE_UPDATED = "node_updated"


class JournalEvent:
    """Minimal event representation."""
    def __init__(self, event_type: EventType, txn: Dict[str, Any]):
        self.event_type = event_type
        self.txn = txn
        self.ts = txn.get("ts", 0.0)
        self.txn_id = txn.get("txn_id")


class JournalTailer:
    """WAL-aware journal tailer: intent → commit → emit."""

    def __init__(self, journal_path: str = ".antigravity/memory/journal.jsonl"):
        self.path = Path(journal_path)
        self.offset = 0
        self._pending: Dict[str, Any] = {}  # txn_id → intent_record
        self.subscribers: List[Callable] = []

    def subscribe(self, callback: Callable) -> None:
        """Register event subscriber: callback(event_type, event)."""
        self.subscribers.append(callback)

    def _emit(self, event_type: EventType, txn: Dict[str, Any]) -> None:
        """Emit semantic event to all subscribers."""
        event = JournalEvent(event_type, txn)
        for sub in self.subscribers:
            try:
                sub(event)
            except Exception as e:
                print(f"Subscriber error: {e}")

    def poll(self) -> None:
        """
        Poll journal: read new entries, update transaction buffer, emit on commit.
        
        Handles:
        - Truncation: if file < offset, reset offset to 0
        - Torn lines: if JSONDecodeError, break and retry next poll
        - Out-of-order records: maintain intent buffer until commit arrives
        """
        if not self.path.exists():
            return

        # Handle truncation (e.g., checkpoint reset)
        file_size = os.path.getsize(self.path)
        if file_size < self.offset:
            self.offset = 0

        with open(self.path, "r", encoding="utf-8") as f:
            f.seek(self.offset)
            while True:
                line = f.readline()
                if not line or not line.endswith("\n"):
                    # Incomplete line (torn write): wait for next poll
                    break

                try:
                    rec = json.loads(line)
                    self._handle_record(rec)
                    self.offset = f.tell()  # Update only after successful parse
                except json.JSONDecodeError:
                    # Torn line: don't update offset, retry next poll
                    break

    def _handle_record(self, rec: Dict[str, Any]) -> None:
        """
        Process WAL record: intent stores txn, commit/rollback derives event.
        """
        rec_type = rec.get("type")
        txn_id = rec.get("txn_id")

        if rec_type == "intent":
            # Store pending transaction
            self._pending[txn_id] = rec

        elif rec_type == "commit":
            # Emit event only when txn commits
            txn = self._pending.pop(txn_id, None)
            if txn:
                self._emit(EventType.NODE_UPDATED, txn)

        elif rec_type == "rollback":
            # Discard pending transaction
            self._pending.pop(txn_id, None)
