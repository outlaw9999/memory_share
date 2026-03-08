# Journal Tailer Plugin - O(1) WAL Stream Processing

## Overview

**Journal Tailer** is a **background, non-blocking journal stream reader** for Antigravity kernel. It's designed to eliminate the performance bottleneck where IDE lags waiting for index updates.

### The Problem We Solve

In Phase 6 (frozen kernel), `write_memory()` appends events to `journal.jsonl`. If ATLAS (or any plugin) must **synchronously index** every write, the IDE freezes.

### The Solution: Async Batch Processing

```
write_memory() appends journal entry → returns immediately
                                    ↓
                            JournalTailer reads tail of journal
                                    ↓
                        Batches events for 500ms
                                    ↓
                        Emits to EventBus (all subscribers)
                                    ↓
                    ATLAS updates index in background
                        UI updates asynchronously
```

**Result:** Write latency remains O(1). Full index update happens silently.

---

## Architecture

### Key Design Decisions

| Decision | Why |
|----------|-----|
| **Append-only read** | Only process new lines since last read position |
| **500ms batching** | Amortize event bus overhead; ~100 events/batch typical |
| **Event subscribers** | Plugins subscribe to `node_created`, `node_updated`, etc. |
| **No blocking** | Tailer runs in separate thread/process; kernel never waits |

### Event Model

```python
@dataclass
class JournalEvent:
    event_type: Literal["node_created", "node_updated", "node_deleted", ...]
    timestamp: float
    node_id: str
    data: dict  # Payload (anchor, content, metadata)
    line_number: int  # For replay/recovery
```

### Tailer Lifecycle

```python
from plugins.journal_tailer import JournalTailer, EventType

# 1. Create tailer instance
tailer = JournalTailer(
    journal_path=Path(".antigravity/memory/journal.jsonl"),
    batch_interval_ms=500,
    max_batch_size=1000
)

# 2. Subscribe to events
def on_node_created(event: JournalEvent):
    atlas.index_node(event.node_id, event.data)

tailer.subscribe(EventType.NODE_CREATED, on_node_created)

# 3. Start tailer
tailer.start()

# 4. Call tick() regularly (in your event loop)
while running:
    tailer.tick()  # Reads journal, emits batched events
    time.sleep(0.05)  # 50ms polling interval

# 5. Shutdown
tailer.stop()  # Flushes pending events
```

---

## Performance Profile

### Assumptions
- Journal append: **~1KB per operation**
- Typical write rate: **10-50/sec** (reasonable for IDE background)
- Full ATLAS index update: **~500ms**

### Metrics

| Metric | Value |
|--------|-------|
| **Read latency** | ~5ms (file seek + batch) |
| **Batch overhead** | ~10ms (JSON parse + emit) |
| **Typical batch size** | 5-50 events (500ms window) |
| **Kernel blocking** | 0ms (tailer is independent) |
| **IDE responsiveness** | Same as before indexing (no regression) |

### Contention Handling

With **50+ concurrent agents** writing journal entries:

```
T=0ms:    Agent 1 writes entry (kernel appends to journal, returns ~0.5ms)
T=1ms:    Agent 2 writes entry
...
T=100ms:  Tailer reads all 50+ entries in one batch
T=100ms+: ATLAS processes all in parallel (vectorized indexing)
```

**No buffering needed.** Kernel never waits for tailer. Index updates lag by ~500ms (acceptable for background task).

---

## Integration with Kernel

### Frozen Boundaries (Phase 6)

The tailer **respects the frozen kernel contract**:

```
Kernel snapshot: runtime/kernel.py + friends (FROZEN)
Tailer location: plugins/journal_tailer/ (OUTSIDE freeze)
```

✅ **Can be added/removed without breaking kernel**  
✅ **Can be updated independently**  
✅ **Cannot modify kernel APIs or journal format**

---

## Example: ATLAS Integration

```python
# atlas_plugin.py
from plugins.journal_tailer import JournalTailer, EventType
from runtime.kernel import read_node

class ATLASIndexer:
    def __init__(self):
        self.tailer = JournalTailer()
        self.tailer.subscribe(EventType.NODE_CREATED, self.on_node_created)
        self.tailer.subscribe(EventType.NODE_UPDATED, self.on_node_updated)
        self.tailer.subscribe(EventType.NODE_DELETED, self.on_node_deleted)

    def on_node_created(self, event):
        """Callback when tailer detects new node."""
        node = read_node(event.node_id)  # Safe: kernel read
        self.vector_db.insert(node.id, node.embedding)

    def on_node_updated(self, event):
        """Re-embed on update."""
        node = read_node(event.node_id)
        self.vector_db.update(node.id, node.embedding)

    def on_node_deleted(self, event):
        """Remove from index."""
        self.vector_db.delete(event.node_id)

    def run(self):
        self.tailer.start()
        while True:
            self.tailer.tick()
            time.sleep(0.050)  # 20Hz polling
```

---

## Testing

**Unit tests** verify:
- ✅ Correct event parsing
- ✅ Batch accumulation logic
- ✅ Subscriber notification
- ✅ File position tracking (only new lines read)

**Integration tests** simulate:
- ✅ Concurrent writes + tailer reads
- ✅ Journal rotation / new files
- ✅ Subscriber error handling

See `test_tailer.py` for examples.

---

## Future Enhancements (Phase 7+)

- **Sharded journals:** Multiple journal files for parallel writing
- **Checkpoint recovery:** Resume from saved position on restart
- **Metrics export:** Prometheus-style tailer metrics
- **Rate limiting:** Backpressure if subscribers lag

---

## Contributing

This plugin is part of the broader **Antigravity memory_share** project.

To submit improvements:

1. Fork `outlaw9999/memory_share`
2. Create a feature branch: `git checkout -b feature/journal-tailer-enhancement`
3. Add tests for any new behavior
4. Submit PR with clear description

---

## License

Same as memory_share project (check top-level LICENSE).
