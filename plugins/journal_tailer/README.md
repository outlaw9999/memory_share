# Journal Tailer Plugin

`JournalTailer` is the Phase 7 bridge between the frozen Phase 6 kernel and background plugins such as ATLAS.

It tails `.antigravity/memory/journal.jsonl`, understands the WAL protocol used by the kernel, and emits semantic events only after a transaction commits.

## Behavior

- Reads incrementally from the last byte offset.
- Persists cursor state and pending transactions atomically in `journal.offset.json`.
- Buffers `intent` records by `txn_id`.
- Emits `EventType.NODE_UPDATED` only when the matching `commit` arrives.
- Drops buffered intents on `rollback`.
- Retries torn or incomplete lines on the next poll without advancing the offset.
- Resets cleanly if the journal is truncated.

## Usage

```python
from plugins.journal_tailer import EventType, JournalTailer

tailer = JournalTailer(".antigravity/memory/journal.jsonl")

def on_event(event):
    if event.event_type is EventType.NODE_UPDATED:
        print(event.txn["target"])

tailer.subscribe(on_event)
tailer.poll()
```
