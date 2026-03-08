"""
WAL-aware journal tailer for the Phase 6 Antigravity kernel.

The tailer consumes append-only journal records shaped like:
`intent -> commit|rollback`.
It buffers intents by transaction id and only emits semantic events
once the transaction is committed.
"""

import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Union


logger = logging.getLogger(__name__)


class EventType(Enum):
    """Semantic events derived from WAL transactions."""

    NODE_UPDATED = "node_updated"


@dataclass
class JournalEvent:
    """Semantic event emitted after a transaction commits."""

    event_type: EventType
    txn: Dict[str, Any]
    ts: float
    txn_id: str | None


class JournalTailer:
    """WAL-aware journal tailer: intent -> commit -> emit."""

    def __init__(self, journal_path: Union[str, Path] = ".antigravity/memory/journal.jsonl"):
        self.path = Path(journal_path)
        self.offset = 0
        self._last_commit_ts = 0.0
        self._pending: Dict[str, Dict[str, Any]] = {}
        self.subscribers: List[Callable[[JournalEvent], None]] = []

    def subscribe(self, callback: Callable[[JournalEvent], None]) -> None:
        """Register a subscriber that receives committed semantic events."""

        self.subscribers.append(callback)

    def _emit(self, event_type: EventType, txn: Dict[str, Any]) -> None:
        """Emit semantic event to all subscribers."""

        event = JournalEvent(
            event_type=event_type,
            txn=txn,
            ts=txn.get("ts", 0.0),
            txn_id=txn.get("txn_id"),
        )
        for sub in self.subscribers:
            try:
                sub(event)
            except Exception as exc:
                print(f"Subscriber error: {exc}")

    def poll(self) -> None:
        """
        Poll the journal and process only newly appended complete lines.

        If the journal is truncated, the tailer resets its offset and
        discards buffered intents because the source of truth changed.
        If the active line is torn or incomplete, the tailer leaves the
        offset unchanged so the next poll can retry the same bytes.
        """

        if not self.path.exists():
            return

        try:
            file_size = os.path.getsize(self.path)
        except OSError:
            return

        if file_size < self.offset:
            self.offset = 0
            self._pending.clear()

        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                handle.seek(self.offset)
                while True:
                    line = handle.readline()
                    if not line or not line.endswith("\n"):
                        break

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        break

                    self._handle_record(record)
                    self.offset = handle.tell()
        except OSError:
            return

    def _handle_record(self, rec: Dict[str, Any]) -> None:
        """Process a WAL record and derive semantic events on commit."""

        rec_type = rec.get("type")
        txn_id = rec.get("txn_id")
        if not txn_id:
            return

        if rec_type == "intent":
            self._pending[txn_id] = rec
        elif rec_type == "commit":
            commit_ts = rec.get("ts", 0.0)
            if commit_ts < self._last_commit_ts:
                logger.warning(
                    "Out-of-order commit detected for txn %s: ts=%s last_commit_ts=%s",
                    txn_id,
                    commit_ts,
                    self._last_commit_ts,
                )
            self._last_commit_ts = max(self._last_commit_ts, commit_ts)
            txn = self._pending.pop(txn_id, None)
            if txn:
                self._emit(EventType.NODE_UPDATED, txn)
        elif rec_type == "rollback":
            self._pending.pop(txn_id, None)
