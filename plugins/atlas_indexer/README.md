# ATLAS Indexer

ATLAS is a Phase 7 plugin that builds a lightweight code graph from WAL-driven file updates.

Semantic contract:

- ATLAS provides replay-safe incremental indexing of the latest workspace snapshot.
- ATLAS does not attempt to reconstruct historical commit states.

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
- Missing files are pruned from the dirty queue before scheduling so branch switches and path churn do not leak queue state.
- Dirty files wait through a short coalescing window so bursty branch-switch or checkout events settle before scanning.
- `AtlasTailerBridge.run_forever()` provides a tiny idle-sleep worker loop without adding async infrastructure.
- A content-hash snapshot guard retries a file if it changes while being scanned.
- Applied transaction ids are retained for a bounded time window to keep replay metadata small.

Current scope:

- dirty file queue
- Python symbol scanning stub
- SQLite-backed symbol table
- WAL bridge from committed journal events to the dirty queue

Future scope:

- Tree-sitter incremental parsing
- graph edges (`imports`, `calls`, `contains`)
- semantic query APIs
