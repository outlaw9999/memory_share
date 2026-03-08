from pathlib import Path
import time
from typing import Optional

from plugins.journal_tailer import EventType, JournalEvent, JournalTailer

from .indexer import AtlasIndexer


class AtlasTailerBridge:
    """Connect committed WAL events to the Atlas dirty queue."""

    def __init__(self, tailer: JournalTailer, indexer: AtlasIndexer):
        self.tailer = tailer
        self.indexer = indexer
        self.tailer.subscribe(self._on_event)

    @classmethod
    def from_workspace(
        cls,
        workspace_root: str = ".",
        *,
        tailer: Optional[JournalTailer] = None,
        indexer: Optional[AtlasIndexer] = None,
    ) -> "AtlasTailerBridge":
        root = Path(workspace_root)
        resolved_tailer = tailer or JournalTailer(root / ".antigravity" / "memory" / "journal.jsonl")
        resolved_indexer = indexer or AtlasIndexer(workspace_root=root)
        return cls(resolved_tailer, resolved_indexer)

    def _on_event(self, event: JournalEvent) -> None:
        if event.event_type is EventType.NODE_UPDATED:
            self.indexer.handle_event(event)

    def pump(self, max_files: Optional[int] = None) -> list[str]:
        """Advance the tailer, then index any files marked dirty by committed WAL events."""

        self.tailer.poll()
        return self.indexer.poll(max_files=max_files)

    def run_forever(self, poll_interval: float = 0.5, max_files: Optional[int] = None) -> None:
        """Continuously pump the tailer and sleep only when the system is idle."""

        if poll_interval < 0:
            raise ValueError("poll_interval must be >= 0")

        while True:
            processed = self.pump(max_files=max_files)
            if not processed:
                time.sleep(poll_interval)
