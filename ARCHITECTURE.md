# .kit Architecture Roadmap (Phase 1-10)

`.kit` is a local-first code intelligence substrate for agents, automation, and developer tooling.

This roadmap ends at Phase 10. At that point, `.kit` is intentionally positioned as a lightweight semantic graph engine backed by SQLite and FTS5.

## Status

As of 2026-03-08:

| Phase | Layer | Capability | Status |
| --- | --- | --- | --- |
| 1-7 | Storage and Indexing | ingest symbols, build call graph, persist SQLite state | implemented |
| 8 | Context Engine | lookup, snippet, unified context retrieval | frozen |
| 9 | Graph Exploration | forward and reverse graph traversal | **completed ✅** |
| 10 | Semantic Graph | precise symbol identity and language-aware adapters | planned |

## Design Principles

1. Local-first storage
   SQLite is the system database. No network service is required for normal operation.
2. Agent-friendly interface
   The primary surface area is a CLI that emits deterministic JSON.
3. Fast retrieval
   FTS5-backed symbol search and bounded graph queries target interactive latency.
4. Layered evolution
   Storage, retrieval, graph reasoning, and semantic identity evolve as separate architectural layers.

## Phase 1-7: Storage and Indexing

These phases establish the data plane used by `kit`.

Current building blocks:

- repository scanning and symbol extraction
- call graph capture
- SQLite persistence
- FTS5 symbol indexing
- adapter boundary between Atlas and Brain

Representative components:

- `plugins/atlas_indexer/graph_store.py`
- `plugins/atlas_indexer/indexer.py`
- `kit.py`
- `kit_adapters.py`

Outcome:

`.kit` becomes a queryable local code database.

## Phase 8: Context Engine

Phase 8 freezes the context-retrieval contract.

Current commands in this layer:

- `kit symbol <query>`
- `kit callers <symbol>`
- `kit snippet <path>:<line>`
- `kit context <symbol>`

Capabilities:

- ranked symbol search
- deterministic snippet retrieval
- unified code context aggregation
- stable JSON envelopes for automation

Question this layer answers:

> What is this symbol?

This layer is frozen for contract stability. Performance improvements and internal refactors are allowed as long as CLI and JSON outputs stay backward compatible.

## Phase 9: Graph Exploration

Phase 9 extends the system from lookup into graph reasoning.

### Forward traversal

Current command:

- `kit related <symbol>`

Purpose:

- explore similar symbols
- inspect direct callers and callees
- inspect nearby module peers

This is the forward exploration primitive used by agents when they need local neighborhood context before editing code.

### Reverse traversal

Planned command:

- `kit impact <symbol>`

Purpose:

- traverse upstream callers
- measure blast radius before refactors
- bound traversal depth for deterministic outputs

Planned implementation:

- recursive SQLite CTE
- deterministic ordering
- configurable depth and result limits

Questions this layer answers:

> What does this symbol interact with?
>
> What might break if I change it?

**Phase 9 is now COMPLETE.** Both `related` and `impact` are available:

- `kit related <symbol>` — neighborhood exploration
- `kit impact <symbol>` — blast radius analysis with cycle-safe recursive CTE

## Phase 10: Semantic Graph

Phase 10 resolves the main correctness limit of the current graph: symbol identity is still name-based.

Current limitation:

```text
parser_a.parse()
parser_b.parse()
```

These can collide if edges are keyed only by symbol name.

Planned direction:

- assign each symbol a stable identity derived from path, name, and scope
- record source spans where available
- migrate call graph edges from name-based references to symbol identifiers
- introduce language-aware adapters that emit stable symbol identity data

Illustrative schema direction:

```sql
symbols(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    file TEXT NOT NULL,
    scope TEXT,
    span_start INTEGER,
    span_end INTEGER
)

calls(
    caller_id INTEGER NOT NULL,
    callee_id INTEGER NOT NULL,
    file TEXT NOT NULL,
    line INTEGER NOT NULL
)
```

Outcome:

`.kit` can answer:

> Which exact symbol is this?

Phase 10 is the planned endpoint of the current architecture roadmap.

## Layered Architecture After Phase 10

```text
Semantic Layer
    language adapters
    symbol identity mapping

Graph Reasoning Layer
    kit related
    kit impact

Context Retrieval Layer
    symbol search
    snippet
    unified context

Storage Layer
    SQLite + FTS5
```

## Performance Targets

Target latencies for a local repository-sized database:

| Operation | Target |
| --- | --- |
| `kit symbol` | < 10 ms |
| `kit context` | < 20 ms |
| `kit related` | < 20 ms |
| `kit impact` | < 30 ms |

These are engineering targets, not frozen guarantees.

## Portable Kit Artifacts

While `.kit` is the **engine**, a `.kit database` is a **portable, shareable artifact**.

### What is a `.kit` Database?

A `.kit` database bundles:

- **Repository snapshot** — code files and metadata
- **Semantic graph** — symbols and call edges
- **FTS index** — full-text search for symbol discovery
- **Identity mapping** — symbol_id → file::scope::name

After Phase 10, each symbol has a stable, language-independent identity:

```
file::scope::name
```

### Instances: `memory_share.kit`

`memory_share.kit` is a concrete instance of a `.kit` database:

```
memory_share.kit
├── .antigravity/atlas/atlas.db
│   ├── symbols (identity-based)
│   ├── calls (identity-based edges)
│   └── symbol_fts (full-text search)
└── code/ (repository snapshot)
```

This makes `memory_share.kit` a **shareable semantic repository memory**:

- **Portable**: can be exchanged between agents, developers, and tools
- **Deterministic**: identity formula is stable across runs
- **Queryable**: all `.kit` commands work on any instance
- **Self-contained**: no external service required

### Product Hierarchy

```
kit engine (CLI + adapters + graph reasoning)
    ↓
kit database format (.antigravity/atlas/atlas.db)
    ↓
portable kit artifact (memory_share.kit, or any .kit instance)
```

---

## Final State

After Phase 10, `.kit` is intentionally scoped as a:

**Local Semantic Code Graph Engine**

Key properties:

- offline-first
- deterministic
- agent-compatible
- minimal infrastructure
- scalable to large repositories through bounded SQLite queries

The primary **product** of `.kit` is portable, shareable semantic code graph artifacts that any agent or developer tool can query without external services or network dependencies.
