# ATLAS Indexer

ATLAS is a Phase 7 plugin that builds a lightweight code graph from WAL-driven file updates.

Pipeline:

```text
JournalTailer
    ->
AtlasTailerBridge
    ->
AtlasIndexer
    ->
Dirty File Queue
    ->
Scanner
    ->
GraphStore
```

Key design rule:

- Events do not trigger immediate parsing.
- Events only mark files as dirty.
- Parsing happens during `AtlasIndexer.poll()` to keep UI-facing workflows light.
- `AtlasTailerBridge.run_forever()` provides a tiny idle-sleep worker loop without adding async infrastructure.

Current scope:

- dirty file queue
- Python symbol scanning stub
- SQLite-backed symbol table
- WAL bridge from committed journal events to the dirty queue

Future scope:

- Tree-sitter incremental parsing
- graph edges (`imports`, `calls`, `contains`)
- semantic query APIs
