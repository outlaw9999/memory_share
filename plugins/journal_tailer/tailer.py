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
from typing import Any, Callable, Dict, List, Tuple, Union


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

    def __init__(
        self,
        journal_path: Union[str, Path] = ".antigravity/memory/journal.jsonl",
        state_path: Union[str, Path, None] = None,
        strict_subscribers: bool = True,
    ):
        self.path = Path(journal_path)
        self.state_path = Path(state_path) if state_path is not None else self.path.with_suffix(".offset.json")
        self.strict_subscribers = strict_subscribers
        self.offset = 0
        self._last_commit_ts = 0.0
        self._file_id: Tuple[int, int] | None = None
        self._pending: Dict[str, Dict[str, Any]] = {}
        self.subscribers: List[Callable[[JournalEvent], None]] = []
        self._load_state()

    def subscribe(self, callback: Callable[[JournalEvent], None]) -> None:
        """Register a subscriber that receives committed semantic events."""

        self.subscribers.append(callback)

    def _emit(self, event_type: EventType, txn: Dict[str, Any]) -> bool:
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
                logger.warning("Subscriber error while handling txn %s: %s", event.txn_id, exc)
                if self.strict_subscribers:
                    return False
        return True

    def _load_state(self) -> None:
        """Load durable tailer state if it exists."""

        if not self.state_path.exists():
            return

        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load tailer state from %s: %s", self.state_path, exc)
            return

        self.offset = int(state.get("offset", 0))
        self._last_commit_ts = float(state.get("last_commit_ts", 0.0))
        pending = state.get("pending", {})
        self._pending = pending if isinstance(pending, dict) else {}

        raw_file_id = state.get("file_id")
        if isinstance(raw_file_id, list) and len(raw_file_id) == 2:
            self._file_id = (int(raw_file_id[0]), int(raw_file_id[1]))

    def _save_state(self) -> None:
        """Persist the current cursor and pending transaction state atomically."""

        state = {
            "offset": self.offset,
            "last_commit_ts": self._last_commit_ts,
            "pending": self._pending,
            "file_id": list(self._file_id) if self._file_id is not None else None,
        }
        tmp_path = self.state_path.with_name(self.state_path.name + ".tmp")

        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with tmp_path.open("w", encoding="utf-8") as handle:
                json.dump(state, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.state_path)
        except OSError as exc:
            logger.warning("Failed to persist tailer state to %s: %s", self.state_path, exc)
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass

    def _current_file_id(self) -> Tuple[int, int] | None:
        """Return a stable identifier for the current journal file."""

        try:
            stat = self.path.stat()
        except OSError:
            return None
        return (stat.st_dev, stat.st_ino)

    def _reset_state(self, file_id: Tuple[int, int] | None) -> None:
        """Reset cursor state when the journal identity changes."""

        self.offset = 0
        self._last_commit_ts = 0.0
        self._pending.clear()
        self._file_id = file_id

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

        current_file_id = self._current_file_id()
        if current_file_id is None:
            return

        if self._file_id is None:
            self._file_id = current_file_id
        elif current_file_id != self._file_id:
            logger.info("Journal file identity changed; resetting tailer cursor")
            self._reset_state(current_file_id)
            self._save_state()

        try:
            file_size = os.path.getsize(self.path)
        except OSError:
            return
        if file_size < self.offset:
            self._reset_state(current_file_id)
            self._save_state()

        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                handle.seek(self.offset)
                should_checkpoint = False
                while True:
                    line_start = handle.tell()
                    line = handle.readline()
                    if not line or not line.endswith("\n"):
                        break

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        break

                    if not self._handle_record(record):
                        logger.warning(
                            "Halting poll at offset %s due to subscriber failure; record will be retried",
                            line_start,
                        )
                        break
                    self.offset = handle.tell()
                    self._file_id = current_file_id
                    should_checkpoint = True
                if should_checkpoint:
                    self._save_state()
        except OSError:
            return

    def _handle_record(self, rec: Dict[str, Any]) -> bool:
        """Process a WAL record and derive semantic events on commit."""

        rec_type = rec.get("type")
        txn_id = rec.get("txn_id")
        if not txn_id:
            return True

        if rec_type == "intent":
            self._pending[txn_id] = rec
            return True
        elif rec_type == "commit":
            txn = self._pending.get(txn_id)
            if txn and not self._emit(EventType.NODE_UPDATED, txn):
                return False
            commit_ts = rec.get("ts", 0.0)
            if commit_ts < self._last_commit_ts:
                logger.warning(
                    "Out-of-order commit detected for txn %s: ts=%s last_commit_ts=%s",
                    txn_id,
                    commit_ts,
                    self._last_commit_ts,
                )
            self._last_commit_ts = max(self._last_commit_ts, commit_ts)
            self._pending.pop(txn_id, None)
            return True
        elif rec_type == "rollback":
            self._pending.pop(txn_id, None)
            return True
        return True
