# Journal Tailer Plugin

`JournalTailer` is the Phase 7 bridge between the frozen Phase 6 kernel and background plugins such as ATLAS.

It tails `.antigravity/memory/journal.jsonl`, understands the real WAL protocol used by the kernel, and emits semantic events only after a transaction commits.

## Behavior

- Reads incrementally from the last byte offset.
- Persists cursor state and pending transactions atomically in `journal.offset.json`.
- Buffers `intent` records by `txn_id`.
- Emits `EventType.NODE_UPDATED` only when the matching `commit` arrives.
- Drops buffered intents on `rollback`.
- Retries torn or incomplete lines on the next poll without advancing the offset.
- Resets cleanly if the journal is truncated.
- Resets and replays from byte `0` if the journal file identity changes.
- Warns if commit timestamps move backward, while still preserving WAL order.
- Halts before checkpointing a failed subscriber delivery when `strict_subscribers=True` (default).

## Protocol

The Phase 6 journal is append-only and uses these record types:

```json
{"type":"intent","txn_id":"...","ts":0.0,"agent":"...","target":"...","op":"update_node","node":{"node_id":"..."},"old_hash":"..."}
{"type":"commit","txn_id":"...","ts":0.0,"new_hash":"..."}
{"type":"rollback","txn_id":"...","ts":0.0,"reason":"..."}
```

The tailer does not emit on `intent`. Downstream plugins only observe committed state.

## Usage

```python
from plugins.journal_tailer import JournalTailer, EventType

tailer = JournalTailer(".antigravity/memory/journal.jsonl")

def on_event(event):
    if event.event_type is EventType.NODE_UPDATED:
        print(event.txn["node"]["node_id"])

tailer.subscribe(on_event)

while True:
    tailer.poll()
```

By default the tailer stores its checkpoint beside the WAL as `journal.offset.json`.
This gives it durable resume behavior across restarts while preserving pending transactions.
Checkpoint state is flushed once per poll after the acknowledged records in that poll, instead of once per WAL record.
Delivery remains at-least-once across crashes because a process can still fail after emit and before the next checkpoint flush.
With the default `strict_subscribers=True`, subscriber failures stop the poll before the failing record is checkpointed, so the record can be retried on the next poll or after restart.

## Boundary

This plugin lives entirely under `plugins/` and does not modify `runtime/`.
That keeps it outside the Phase 6 freeze boundary defined by `ARCHITECTURE_FREEZE.md`.
